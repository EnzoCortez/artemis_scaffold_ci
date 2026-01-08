from typing import Iterable, List, Generator, Any

def chunked(iterable: Iterable[Any], size: int) -> Generator[List[Any], None, None]:
    """
    Divide un iterable en bloques de tamaño fijo.
    Evita usar listas gigantes en memoria y reduce locks en DB.
    """
    chunk = []
    for item in iterable:
        chunk.append(item)
        if len(chunk) >= size:
            yield chunk
            chunk = []
    if chunk:
        yield chunk
