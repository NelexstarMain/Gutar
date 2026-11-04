"""midi_out.py - zapis listy nut jako plik MIDI (SMF format 0, 480 tików na ćwierćnutę, 120 BPM = 960 tików na sekundę)."""
TICKS_PER_SEC = 960


def _vlq(n):
    out = [n & 127]
    n >>= 7
    while n:
        out.append((n & 127) | 128)
        n >>= 7
    return bytes(reversed(out))


def notes_to_midi(notes, program=24):
    """notes: obiekty z polami pitch, onset, offset, velocity (0..1 albo None). program 24 = gitara nylonowa."""
    ev = []
    for n in notes:
        p = int(round(n.pitch))
        if not 0 <= p <= 127:
            continue
        v = 80 if n.velocity is None else max(1, min(127, int(round(n.velocity * 127))))
        t0 = int(round(n.onset * TICKS_PER_SEC))
        t1 = max(t0 + 1, int(round(n.offset * TICKS_PER_SEC)))
        ev.append((t0, 1, bytes([0x90, p, v])))
        ev.append((t1, 0, bytes([0x80, p, 0])))  # koniec przed początkiem tej samej wysokości w tym samym tiku
    ev.sort(key=lambda e: (e[0], e[1]))
    trk = bytearray(b'\x00\xff\x51\x03\x07\xa1\x20' + b'\x00\xc0' + bytes([program]))  # tempo 500000 us, program
    t = 0
    for tick, _, data in ev:
        trk += _vlq(tick - t) + data
        t = tick
    trk += b'\x00\xff\x2f\x00'
    return b'MThd' + (6).to_bytes(4, 'big') + (0).to_bytes(2, 'big') + (1).to_bytes(2, 'big') + (480).to_bytes(2, 'big') + \
        b'MTrk' + len(trk).to_bytes(4, 'big') + bytes(trk)
