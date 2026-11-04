#!/usr/bin/env python3
"""preannotate.py - wstępny opis nagrań modelem (do ręcznej poprawy zamiast pisania nut od zera).

  python3 tools/gen6/piezo/preannotate.py CKPT FOLDER_Z_WAV [--out FOLDER] [--th-onset 0.5]

Dla każdego <nazwa>.wav zapisuje <nazwa>.csv (onset, offset, pitch) i <nazwa>.mid. Najlepiej dać nagranie z mikrofonu (nagrane
równocześnie z piezo, tej samej gry) i skopiować wynik pod nazwą nagrania piezo: model trafia dużo lepiej z mikrofonu niż z piezo,
a poprawiasz tylko błędy (CSV w arkuszu / plik MIDI w edytorze, np. MuseScore, Reaper, LMMS).
"""
import argparse, os, sys, csv
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
sys.path.insert(0, ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('ckpt'); ap.add_argument('folder'); ap.add_argument('--out')
    ap.add_argument('--th-onset', type=float)
    a = ap.parse_args()
    import torch
    from tools.gen6.config import Config
    from tools.gen6.model import Gen6
    from tools.gen6.audio import load_audio
    from tools.gen6.features import hcqt
    from tools.gen6.decode import decode_notes
    from tools.gen6.server.midi_out import notes_to_midi
    st = torch.load(a.ckpt, weights_only=False, map_location='cpu')
    cfg = Config.from_dict(st['config'])
    if a.th_onset:
        cfg.decode.th_onset = a.th_onset
    net = Gen6(cfg); net.load_state_dict(st['net']); net.eval()
    out = a.out or a.folder
    os.makedirs(out, exist_ok=True)
    for f in sorted(os.listdir(a.folder)):
        if not f.lower().endswith('.wav'):
            continue
        x = load_audio(os.path.join(a.folder, f), cfg.features.sr, cfg.features.frontend)
        with torch.no_grad():
            p = net.predict(hcqt(x, cfg.features))
        notes = decode_notes(p, cfg.features, cfg.decode, cfg.labels)
        base = os.path.join(out, f[:-4])
        with open(base + '.csv', 'w', newline='') as fo:
            w = csv.writer(fo); w.writerow(['onset', 'offset', 'pitch'])
            for n in notes:
                w.writerow(['%.3f' % n.onset, '%.3f' % n.offset, int(round(n.pitch))])
        for n in notes:
            n.velocity = None
        open(base + '.mid', 'wb').write(notes_to_midi(notes))
        print('%s: %d nut' % (f, len(notes)))


if __name__ == '__main__':
    main()
