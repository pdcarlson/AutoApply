"""Untangles a PDF page's side-by-side columns into lines that read in order."""
from server.resume.line_text import indent
from server.resume.pdf_lines import FOOTER_RE, clean_line
from server.resume.section_headers import header_name

# A chunk of lines, and whether it starts outside any section (a sidebar's own stream)
Chunk = tuple[list[str], bool]

_MIN_GUTTER = 3  # blank characters
_MIN_BLOCK_LINES = 3


def page_chunks(lines: list[str]) -> list[Chunk]:
    """Return one page's layout lines as chunks, with their columns untangled."""
    lines = [clean_line(line) for line in lines]
    lines = [line for line in lines if line.strip() and not FOOTER_RE.match(line)]
    if not lines:
        return []
    chunks: list[Chunk] = []
    plain: list[str] = []
    position = 0
    for start, end, emitted in _chosen_blocks(lines):
        plain.extend(lines[position:start])
        if plain:
            chunks.append((plain, False))
            plain = []
        chunks.extend(emitted)
        position = end
    plain.extend(lines[position:])
    if plain:
        chunks.append((plain, False))
    return chunks


def _chosen_blocks(lines: list[str]) -> list[tuple[int, int, list[Chunk]]]:
    """Return the (start, end, chunks) of each gutter block to untangle, in page order.

    Only blocks that change something (sidebars, label columns) count; a column of dates is
    read as it is. Longest first, so a small block can't cut a sidebar in two.
    """
    width = max(len(line) for line in lines) + 1
    blocks = []
    for start in range(len(lines)):
        found = _find_block(lines, start, width)
        if found and found[0] - start >= _MIN_BLOCK_LINES:
            emitted = _emit_block(lines[start:found[0]], found[1], found[2])
            if emitted != [(lines[start:found[0]], False)]:
                blocks.append((found[0] - start, start, found[0], emitted))
    taken = [False] * len(lines)
    chosen = []
    for _, start, end, emitted in sorted(blocks, key=lambda block: (-block[0], block[1])):
        if not any(taken[start:end]):
            taken[start:end] = [True] * (end - start)
            chosen.append((start, end, emitted))
    return sorted(chosen, key=lambda block: block[0])


def _find_block(lines: list[str], start: int, width: int) -> tuple[int, int, int] | None:
    """Return the longest run of lines from `start` sharing a gutter: (end, gap, column).

    A gutter is 3+ blank characters, in every line, with text on its left in 2+ lines and text on
    its right in 2+ lines. `gap` is where the blank band starts, `column` where it ends.
    """
    blank = [True] * width
    first = [indent(line) for line in lines]
    ends = [len(line) for line in lines]
    best = None
    for last in range(start, len(lines)):
        for position, char in enumerate(lines[last][:width]):
            if char != " ":
                blank[position] = False
        runs = _blank_runs(blank, width)
        if not runs:
            break
        if last - start < 2:
            continue
        gutter = _best_gutter(runs, first[start:last + 1], ends[start:last + 1])
        if gutter:
            best = (last + 1, *gutter)
    return best


def _best_gutter(runs: list[tuple[int, int]], first: list[int],
                 ends: list[int]) -> tuple[int, int] | None:
    """Return the (gap, column) of the band with the most text on both sides, or None.

    `first` and `ends` are where each line of the block starts and ends.
    """
    scored = []
    for gap, column in runs:
        left = sum(start < gap for start in first)
        right = sum(end > column for end in ends)
        if left >= 2 and right >= 2:
            scored.append((min(left, right), column - gap, gap, column))
    if not scored:
        return None
    _, _, gap, column = max(scored)
    return gap, column


def _blank_runs(blank: list[bool], width: int) -> list[tuple[int, int]]:
    """Return the (start, end) of each band of 3+ blank positions that has text to its right."""
    runs = []
    position = _MIN_GUTTER
    while position < width:
        if blank[position]:
            end = position
            while end < width and blank[end]:
                end += 1
            if end - position >= _MIN_GUTTER and end < width:
                runs.append((position, end))
            position = end
        else:
            position += 1
    return runs


def _dedent(parts: list[str]) -> list[str]:
    """Return the parts with their shared indent removed."""
    indents = [indent(part) for part in parts if part.strip()]
    cut = min(indents) if indents else 0
    return [part[cut:].rstrip() for part in parts]


def _emit_block(block: list[str], gap: int, column: int) -> list[Chunk]:
    """Return one gutter block as chunks of lines in reading order.

    When both sides have section headers (a sidebar resume) the wider side is read first, then
    the other; when only the left side has them (a label column) each label goes on its own line
    before its text; otherwise (a column of dates, a skills table) the lines stay as they are.
    """
    left = [line[:gap].rstrip() for line in block]
    right = _dedent([line[column:] if len(line) > column else "" for line in block])
    left_cells = [part for part in left if part.strip()]
    left_headers = sum(bool(header_name(part)) for part in left_cells)
    right_headers = any(header_name(part) for part in right if part.strip())
    if left_headers and right_headers:  # a sidebar: two separate streams, main one first
        streams = [[part for part in side if part.strip()] for side in (left, right)]
        streams.sort(key=lambda stream: -sum(len(part.strip()) for part in stream))
        return [(stream, True) for stream in streams]
    # a label column: "EXPERIENCE   Senior Engineer ..."
    if left_cells and left_headers >= 0.6 * len(left_cells):
        rows: list[str] = []
        for left_part, right_part in zip(left, right):
            rows.extend(part for part in (left_part, right_part) if part.strip())
        return [(rows, False)]
    return [(block, False)]
