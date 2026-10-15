# Biblioteca estándar inicial

Los módulos se distribuyen con W0 y se importan mediante rutas `std/nombre`.

- `std/io`: `read_text(path)` y `write_text(path, content)` devuelven canales `IoError`. El texto debe ser UTF-8 válido; los NUL forman parte del contenido.
- `std/text`: `join(parts, separator)`, `pad_left(text, width, fill)` y `lines(text)`. Los anchos cuentan escalares Unicode, no columnas visuales ni grafemas. `lines` admite LF y CRLF, y omite una línea vacía final. Un relleno de varios caracteres puede superar el ancho solicitado.
- `std/algorithms`: `map[T,R]`, `fold[T,R]` y `sort[T]`. El ordenamiento es estable, usa mezcla, requiere un comparador estricto y devuelve una lista independiente. Su complejidad es O(n log n) y usa memoria auxiliar O(n); no modifica la entrada.
- `std/bytes`: `encode(text)` y `decode(bytes)`. El decoder rechaza bytes fuera de rango, secuencias truncadas, continuaciones incorrectas, overlong encodings, sustitutos y valores superiores a U+10FFFF. `Utf8Error.offset` identifica el byte que falló.

Esta biblioteca es pequeña. La concatenación repetida de strings todavía copia contenido; `join`, `pad_left` y `decode` no deben presentarse como soluciones eficientes para flujos grandes. No hay red, streams binarios, locales ni normalización Unicode.
