"""Estructuras de datos dinámicas implementadas desde cero (sin usar list/dict como
estructura principal): lista doblemente enlazada, pila, cola, tabla hash con
encadenamiento y árbol binario de búsqueda con recursión."""
from __future__ import annotations
import unicodedata


def normalizar(texto: str) -> str:
    """Minúsculas y sin tildes, para ordenar y buscar de forma uniforme."""
    t = unicodedata.normalize("NFD", texto.strip().casefold())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


class Nodo:
    __slots__ = ("dato", "sig", "ant")

    def __init__(self, dato):
        self.dato, self.sig, self.ant = dato, None, None


class ListaDoble:
    """Lista doblemente enlazada. Se usa para los contactos de emergencia de cada
    persona (tamaño variable, inserción ordenada por prioridad)."""

    def __init__(self):
        self.cabeza = self.cola = None
        self._n = 0

    def __len__(self):
        return self._n

    def __iter__(self):
        n = self.cabeza
        while n:
            yield n.dato
            n = n.sig

    def agregar_final(self, dato):
        nodo = Nodo(dato)
        if self.cola is None:
            self.cabeza = self.cola = nodo
        else:
            nodo.ant, self.cola.sig = self.cola, nodo
            self.cola = nodo
        self._n += 1

    def insertar_ordenado(self, dato, clave):
        """Inserta antes del primer nodo con clave mayor (estable). O(n)."""
        nuevo, actual = Nodo(dato), self.cabeza
        while actual and clave(actual.dato) <= clave(dato):
            actual = actual.sig
        if actual is None:
            self.agregar_final(dato)
            return
        nuevo.sig, nuevo.ant = actual, actual.ant
        if actual.ant:
            actual.ant.sig = nuevo
        else:
            self.cabeza = nuevo
        actual.ant = nuevo
        self._n += 1

    def eliminar_si(self, pred) -> int:
        """Elimina todos los nodos que cumplan pred; devuelve la cantidad."""
        borrados, n = 0, self.cabeza
        while n:
            sig = n.sig
            if pred(n.dato):
                if n.ant: n.ant.sig = n.sig
                else: self.cabeza = n.sig
                if n.sig: n.sig.ant = n.ant
                else: self.cola = n.ant
                self._n -= 1
                borrados += 1
            n = sig
        return borrados

    def a_lista(self):
        return list(self)


class Pila:
    """Pila (LIFO) enlazada: historial para la función Deshacer."""

    def __init__(self):
        self._tope, self._n = None, 0

    def __len__(self):
        return self._n

    def vacia(self):
        return self._tope is None

    def apilar(self, dato):
        nodo = Nodo(dato)
        nodo.sig, self._tope = self._tope, nodo
        self._n += 1

    def desapilar(self):
        if self._tope is None:
            raise IndexError("Pila vacía")
        nodo = self._tope
        self._tope, self._n = nodo.sig, self._n - 1
        return nodo.dato

    def ver_tope(self):
        return None if self._tope is None else self._tope.dato


class Cola:
    """Cola (FIFO) enlazada: búfer de eventos de bitácora pendientes de guardar."""

    def __init__(self):
        self._ini = self._fin = None
        self._n = 0

    def __len__(self):
        return self._n

    def vacia(self):
        return self._ini is None

    def encolar(self, dato):
        nodo = Nodo(dato)
        if self._fin is None:
            self._ini = self._fin = nodo
        else:
            self._fin.sig = nodo
            self._fin = nodo
        self._n += 1

    def desencolar(self):
        if self._ini is None:
            raise IndexError("Cola vacía")
        nodo = self._ini
        self._ini = nodo.sig
        if self._ini is None:
            self._fin = None
        self._n -= 1
        return nodo.dato


class TablaHash:
    """Tabla hash con encadenamiento (listas enlazadas simples) y redimensionado
    automático cuando el factor de carga supera 0.75. Índice cédula -> Persona."""

    def __init__(self, capacidad=16):
        self._cap = capacidad
        self._b = [None] * capacidad
        self._n = 0

    @staticmethod
    def _hash(clave: str) -> int:           # djb2
        h = 5381
        for c in clave:
            h = ((h << 5) + h + ord(c)) & 0xFFFFFFFF
        return h

    def __len__(self):
        return self._n

    def _pos(self, clave):
        return self._hash(clave) % self._cap

    def poner(self, clave, valor):
        i = self._pos(clave)
        n = self._b[i]
        while n:
            if n.dato[0] == clave:
                n.dato = (clave, valor)
                return
            n = n.sig
        nodo = Nodo((clave, valor))
        nodo.sig, self._b[i] = self._b[i], nodo
        self._n += 1
        if self._n / self._cap > 0.75:
            self._redimensionar()

    def obtener(self, clave, defecto=None):
        n = self._b[self._pos(clave)]
        while n:
            if n.dato[0] == clave:
                return n.dato[1]
            n = n.sig
        return defecto

    def __contains__(self, clave):
        sentinel = object()
        return self.obtener(clave, sentinel) is not sentinel

    def quitar(self, clave) -> bool:
        i = self._pos(clave)
        prev, n = None, self._b[i]
        while n:
            if n.dato[0] == clave:
                if prev: prev.sig = n.sig
                else: self._b[i] = n.sig
                self._n -= 1
                return True
            prev, n = n, n.sig
        return False

    def _redimensionar(self):
        viejos = self._b
        self._cap *= 2
        self._b, self._n = [None] * self._cap, 0
        for n in viejos:
            while n:
                self.poner(*n.dato)
                n = n.sig

    def valores(self):
        for n in self._b:
            while n:
                yield n.dato[1]
                n = n.sig


class _NodoArbol:
    __slots__ = ("clave", "valores", "izq", "der")

    def __init__(self, clave, valor):
        self.clave, self.valores, self.izq, self.der = clave, [valor], None, None


class ArbolBST:
    """Árbol binario de búsqueda (recursivo) indexado por 'apellidos nombre'
    normalizado. Permite listado ordenado (in-orden) y búsqueda por prefijo."""

    def __init__(self):
        self.raiz, self._n = None, 0

    def __len__(self):
        return self._n

    # --- inserción / eliminación -------------------------------------------
    def insertar(self, clave, valor):
        self.raiz = self._ins(self.raiz, clave, valor)

    def _ins(self, nodo, clave, valor):
        if nodo is None:
            self._n += 1
            return _NodoArbol(clave, valor)
        if clave < nodo.clave:
            nodo.izq = self._ins(nodo.izq, clave, valor)
        elif clave > nodo.clave:
            nodo.der = self._ins(nodo.der, clave, valor)
        elif valor not in nodo.valores:      # homónimos: misma clave, varios valores
            nodo.valores.append(valor)
        return nodo

    def eliminar(self, clave, valor):
        self.raiz = self._del(self.raiz, clave, valor)

    def _del(self, nodo, clave, valor):
        if nodo is None:
            return None
        if clave < nodo.clave:
            nodo.izq = self._del(nodo.izq, clave, valor)
        elif clave > nodo.clave:
            nodo.der = self._del(nodo.der, clave, valor)
        else:
            if valor in nodo.valores:
                nodo.valores.remove(valor)
            if nodo.valores:
                return nodo
            self._n -= 1
            if nodo.izq is None: return nodo.der
            if nodo.der is None: return nodo.izq
            suc = nodo.der
            while suc.izq:
                suc = suc.izq
            nodo.clave, nodo.valores = suc.clave, suc.valores
            self._n += 1                      # el sucesor se elimina a continuación
            nodo.der = self._del_clave(nodo.der, suc.clave)
        return nodo

    def _del_clave(self, nodo, clave):
        if nodo is None: return None
        if clave < nodo.clave:
            nodo.izq = self._del_clave(nodo.izq, clave)
        elif clave > nodo.clave:
            nodo.der = self._del_clave(nodo.der, clave)
        else:
            self._n -= 1
            if nodo.izq is None: return nodo.der
            if nodo.der is None: return nodo.izq
            suc = nodo.der
            while suc.izq: suc = suc.izq
            nodo.clave, nodo.valores = suc.clave, suc.valores
            self._n += 1
            nodo.der = self._del_clave(nodo.der, suc.clave)
        return nodo

    # --- construcción balanceada a partir de datos ya ordenados ---------------
    @classmethod
    def desde_ordenados(cls, pares):
        """pares: lista [(clave, valor)] ordenada por clave. Construye un árbol de
        altura O(log n) mediante recursión (evita degenerar en lista)."""
        arbol = cls()
        agrupados = []
        for k, v in pares:
            if agrupados and agrupados[-1][0] == k:
                agrupados[-1][1].append(v)
            else:
                agrupados.append((k, [v]))

        def construir(lo, hi):
            if lo > hi:
                return None
            m = (lo + hi) // 2
            nodo = _NodoArbol(agrupados[m][0], agrupados[m][1][0])
            nodo.valores = list(agrupados[m][1])
            nodo.izq, nodo.der = construir(lo, m - 1), construir(m + 1, hi)
            return nodo
        arbol.raiz = construir(0, len(agrupados) - 1)
        arbol._n = len(agrupados)
        return arbol

    # --- consultas ---------------------------------------------------------
    def en_orden(self):
        res = []
        self._inorden(self.raiz, res)
        return res

    def _inorden(self, nodo, res):
        if nodo:
            self._inorden(nodo.izq, res)
            res.extend(nodo.valores)
            self._inorden(nodo.der, res)

    def buscar_prefijo(self, prefijo):
        res = []
        self._pref(self.raiz, prefijo, res)
        return res

    def _pref(self, nodo, p, res):
        if nodo is None:
            return
        if nodo.clave.startswith(p):
            self._pref(nodo.izq, p, res)
            res.extend(nodo.valores)
            self._pref(nodo.der, p, res)
        elif p < nodo.clave:
            self._pref(nodo.izq, p, res)
        else:
            self._pref(nodo.der, p, res)

    def buscar_subcadena(self, sub):
        """Coincidencia parcial en cualquier posición (recorrido completo, O(n))."""
        res = []
        self._sub(self.raiz, sub, res)
        return res

    def _sub(self, nodo, s, res):
        if nodo:
            self._sub(nodo.izq, s, res)
            if s in nodo.clave:
                res.extend(nodo.valores)
            self._sub(nodo.der, s, res)

    def altura(self):
        def h(n):
            return 0 if n is None else 1 + max(h(n.izq), h(n.der))
        return h(self.raiz)
