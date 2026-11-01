"""ダイスオークションの効果音を標準ライブラリだけで合成する。
使い方: python synth.py <出力フォルダ> <style: real|pop|retro> [reel]
"""
import math, random, struct, sys, wave, os

SR = 44100

def zeros(sec): return [0.0] * int(SR * sec)

def mix(dst, src, at=0.0, gain=1.0):
    o = int(at * SR)
    need = o + len(src)
    if need > len(dst): dst.extend([0.0] * (need - len(dst)))
    for i, v in enumerate(src): dst[o + i] += v * gain
    return dst

def env_exp(n, tau):
    return [math.exp(-i / (tau * SR)) for i in range(n)]

def damped(freq, tau, dur, phase=0.0, amp=1.0):
    n = int(dur * SR)
    return [amp * math.exp(-i / (tau * SR)) * math.sin(2 * math.pi * freq * i / SR + phase) for i in range(n)]

def noise(dur, rng):
    return [rng.uniform(-1, 1) for _ in range(int(dur * SR))]

def biquad_bp(x, f, q):
    w = 2 * math.pi * f / SR; a = math.sin(w) / (2 * q)
    b0, b1, b2 = a, 0, -a; a0, a1, a2 = 1 + a, -2 * math.cos(w), 1 - a
    b0, b1, b2, a1, a2 = b0 / a0, b1 / a0, b2 / a0, a1 / a0, a2 / a0
    y = []; x1 = x2 = y1 = y2 = 0.0
    for v in x:
        o = b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, v, y1, o; y.append(o)
    return y

def lowpass(x, f):
    a = math.exp(-2 * math.pi * f / SR); y = []; p = 0.0
    for v in x: p = (1 - a) * v + a * p; y.append(p)
    return y

def highpass(x, f):
    lp = lowpass(x, f); return [a - b for a, b in zip(x, lp)]

def mul(x, e): return [a * b for a, b in zip(x, e)]

def square(freq, dur, duty=0.5, amp=1.0):
    n = int(dur * SR); out = []
    for i in range(n):
        ph = (freq * i / SR) % 1.0
        out.append(amp if ph < duty else -amp)
    return out

def sweep_square(f0, f1, dur, amp=1.0, duty=0.5):
    n = int(dur * SR); out = []; ph = 0.0
    for i in range(n):
        f = f0 + (f1 - f0) * i / n; ph = (ph + f / SR) % 1.0
        out.append(amp if ph < duty else -amp)
    return out

def bell(freq, dur, amp=1.0, bright=1.0):
    # ベル: 少しずれた倍音を重ねる
    out = zeros(dur)
    for mult, a, tau in [(1, 1, .5), (2.01, .5 * bright, .25), (3.0, .3 * bright, .15), (4.17, .2 * bright, .08)]:
        mix(out, damped(freq * mult, tau * dur / .6, dur, amp=a * amp))
    return out

def marimba(freq, dur, amp=1.0):
    out = zeros(dur)
    mix(out, damped(freq, .18, dur, amp=amp))
    mix(out, damped(freq * 4, .03, dur, amp=amp * .35))
    mix(out, damped(freq * 10, .008, dur, amp=amp * .15))
    return out

NOTE = lambda n: 440 * 2 ** ((n - 69) / 12)

# ---------------- 各効果音 ----------------
def clack(rng, style, base=1.0, amp=1.0):
    """チップが1枚、卓に置かれる音"""
    if style == 'real':
        out = zeros(.12)
        for k, f in enumerate([2700, 4300, 6100]):
            mix(out, damped(f * base * rng.uniform(.97, 1.03), .012 - k * .003, .12, rng.uniform(0, 6), amp=[1, .6, .35][k] * amp))
        tr = mul(highpass(noise(.012, rng), 2500), env_exp(int(.012 * SR), .002))
        mix(out, tr, 0, .8 * amp)
        # 跳ね返りのもう一音
        second = zeros(.06)
        mix(second, damped(3300 * base, .008, .06, amp=.45 * amp))
        mix(out, second, .022)
        return out
    if style == 'pop':
        out = zeros(.18)
        mix(out, marimba(NOTE(84) * base, .18, amp))
        return out
    # retro
    n = int(.05 * SR)
    return mul(sweep_square(1800 * base, 900 * base, .05, amp * .5, .25), env_exp(n, .02))

def s_chip(rng, style):
    return clack(rng, style, rng.uniform(.95, 1.05))

def s_bet(rng, style):
    out = zeros(.5)
    if style == 'retro':
        for i, n in enumerate([72, 76, 79, 84]):
            mix(out, mul(square(NOTE(n), .06, .25, .35), env_exp(int(.06 * SR), .05)), i * .055)
        return out
    for i in range(6):
        mix(out, clack(rng, style, 1 - i * .02 if style == 'real' else [1, 1.12, 1.26, 1.33, 1.5, 1.68][i], .75 + i * .05), i * (.045 if style == 'real' else .06))
    if style == 'real':
        sl = mul(biquad_bp(noise(.25, rng), 1800, 1.2), env_exp(int(.25 * SR), .08))
        mix(out, sl, 0, .25)
    return out

def s_reveal(rng, style):
    out = zeros(.9)
    if style == 'retro':
        mix(out, mul(sweep_square(300, 1500, .18, .35), env_exp(int(.18 * SR), .2)))
        mix(out, mul(square(NOTE(88), .3, .5, .3), env_exp(int(.3 * SR), .12)), .2)
        return out
    # めくる音(ノイズのスイープ)
    n = noise(.28, rng); sw = []
    seg = int(.02 * SR)
    for i in range(0, len(n), seg):
        f = 600 + 2600 * i / len(n)
        sw += biquad_bp(n[i:i + seg], f, 2.5)
    mix(out, mul(sw, [math.sin(math.pi * i / len(sw)) for i in range(len(sw))]), 0, .5 if style == 'real' else .3)
    if style == 'real': mix(out, bell(NOTE(88), .6, .35), .22)
    else: mix(out, marimba(NOTE(91), .5, .5), .22)
    return out

def s_lot(rng, style):
    """落札"""
    out = zeros(1.0)
    notes = [79, 84, 88]
    for i, nn in enumerate(notes):
        if style == 'real': mix(out, bell(NOTE(nn), .7, .4), i * .09)
        elif style == 'pop': mix(out, marimba(NOTE(nn), .5, .5), i * .09)
        else: mix(out, mul(square(NOTE(nn), .12, .25, .3), env_exp(int(.12 * SR), .08)), i * .08)
    return out

def s_write(rng, style):
    """面に書き込む(スタンプ)"""
    out = zeros(.4)
    if style == 'retro':
        mix(out, mul(sweep_square(400, 120, .12, .45), env_exp(int(.12 * SR), .06)))
        return out
    mix(out, damped(140 if style == 'real' else 220, .05, .3, amp=.9))
    mix(out, mul(lowpass(noise(.06, rng), 1500), env_exp(int(.06 * SR), .015)), 0, .7)
    if style == 'pop': mix(out, marimba(NOTE(76), .3, .35), .02)
    return out

def s_roll(rng, style):
    """ダイスが転がる"""
    out = zeros(1.0)
    if style == 'retro':
        t = 0.0
        for i in range(9):
            mix(out, mul(noise(.03, rng), env_exp(int(.03 * SR), .008)), t, .4 * (1 - i / 12))
            t += .05 + i * .012
        return out
    t = 0.0
    for i in range(10):
        a = .9 * (1 - i / 13)
        if style == 'real':
            hit = zeros(.08)
            for f in [rng.uniform(900, 1300), rng.uniform(1900, 2500), rng.uniform(3200, 3800)]:
                mix(hit, damped(f, .01, .08, rng.uniform(0, 6), amp=a * .5))
            mix(hit, mul(biquad_bp(noise(.02, rng), 1500, 1), env_exp(int(.02 * SR), .004)), 0, a)
        else:
            hit = marimba(NOTE(rng.choice([72, 74, 76, 79])), .1, a * .4)
        mix(out, hit, t)
        t += rng.uniform(.035, .06) + i * .012
    return out

def s_hit(rng, style):
    out = zeros(.45)
    if style == 'retro':
        mix(out, mul(noise(.2, rng), env_exp(int(.2 * SR), .05)), 0, .5)
        mix(out, mul(sweep_square(220, 60, .2, .4), env_exp(int(.2 * SR), .08)))
        return out
    body = [math.sin(2 * math.pi * (110 - 60 * i / (.3 * SR)) * i / SR) * math.exp(-i / (.08 * SR)) for i in range(int(.3 * SR))]
    mix(out, body, 0, 1.0 if style == 'real' else .7)
    mix(out, mul(lowpass(noise(.15, rng), 2500 if style == 'real' else 900), env_exp(int(.15 * SR), .03)), 0, .6)
    return out

def s_heal(rng, style):
    out = zeros(.9)
    for i, nn in enumerate([76, 81, 85, 88]):
        if style == 'real': mix(out, bell(NOTE(nn), .45, .25, .6), i * .06)
        elif style == 'pop': mix(out, marimba(NOTE(nn + 12), .3, .35), i * .06)
        else: mix(out, mul(square(NOTE(nn), .08, .5, .22), env_exp(int(.08 * SR), .05)), i * .05)
    return out

def s_barrier(rng, style):
    out = zeros(.8)
    if style == 'retro':
        mix(out, mul(square(NOTE(96), .25, .125, .3), env_exp(int(.25 * SR), .1)))
        return out
    for f, a, tau in [(1480, .5, .3), (2390, .35, .22), (3710, .25, .15), (5120, .15, .08)]:
        mix(out, damped(f * (1 if style == 'real' else .5), tau, .8, amp=a))
    return out

def s_turn(rng, style):
    out = zeros(.6)
    for i, nn in enumerate([84, 91]):
        if style == 'real': mix(out, bell(NOTE(nn), .4, .25), i * .1)
        elif style == 'pop': mix(out, marimba(NOTE(nn), .3, .4), i * .1)
        else: mix(out, mul(square(NOTE(nn), .07, .25, .25), env_exp(int(.07 * SR), .05)), i * .09)
    return out

def s_win(rng, style):
    out = zeros(2.2)
    seq = [(72, 0), (76, .12), (79, .24), (84, .36)]
    chord = [72, 76, 79, 84, 88]
    for nn, t in seq:
        if style == 'real': mix(out, bell(NOTE(nn), .6, .35), t)
        elif style == 'pop': mix(out, marimba(NOTE(nn), .4, .5), t)
        else: mix(out, mul(square(NOTE(nn), .11, .25, .25), env_exp(int(.11 * SR), .1)), t)
    for nn in chord:
        if style == 'real': mix(out, bell(NOTE(nn), 1.6, .22), .55)
        elif style == 'pop': mix(out, marimba(NOTE(nn), 1.0, .3), .55)
        else: mix(out, mul(square(NOTE(nn), .6, .5, .12), env_exp(int(.6 * SR), .3)), .55)
    if style == 'real':
        for i in range(8): mix(out, clack(rng, 'real', rng.uniform(.9, 1.1), .35), .6 + i * .05)
    return out

def s_lose(rng, style):
    out = zeros(1.8)
    for i, nn in enumerate([76, 72, 69, 64]):
        t = i * .22
        if style == 'real': mix(out, bell(NOTE(nn - 12), .8, .35, .5), t)
        elif style == 'pop': mix(out, marimba(NOTE(nn - 12), .6, .5), t)
        else: mix(out, mul(square(NOTE(nn - 12), .18, .5, .22), env_exp(int(.18 * SR), .15)), t)
    return out

SOUNDS = {'chip': s_chip, 'bet': s_bet, 'reveal': s_reveal, 'lot': s_lot, 'write': s_write, 'roll': s_roll,
          'hit': s_hit, 'heal': s_heal, 'barrier': s_barrier, 'turn': s_turn, 'win': s_win, 'lose': s_lose}

def normalize(x, peak=.85):
    m = max(1e-9, max(abs(v) for v in x)); g = peak / m
    # 末尾の無音を切る
    end = len(x)
    while end > 1 and abs(x[end - 1]) * g < 1e-4: end -= 1
    y = [v * g for v in x[:end]]
    fade = min(len(y), int(.01 * SR))
    for i in range(fade): y[-1 - i] *= i / fade
    return y

def write_wav(path, x):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(b''.join(struct.pack('<h', int(max(-1, min(1, v)) * 32767)) for v in x))

if __name__ == '__main__':
    outdir, style = sys.argv[1], sys.argv[2]
    reel = len(sys.argv) > 3
    os.makedirs(outdir, exist_ok=True)
    rng = random.Random(7)
    if reel:
        order = ['chip', 'chip', 'chip', 'bet', 'reveal', 'lot', 'write', 'roll', 'hit', 'heal', 'barrier', 'win']
        out = zeros(.2); t = .2
        for name in order:
            s = normalize(SOUNDS[name](rng, style), .7)
            mix(out, s, t)
            t += len(s) / SR + (.12 if name == 'chip' else .45)
        write_wav(os.path.join(outdir, f'reel_{style}.wav'), normalize(out, .85))
    else:
        for name, fn in SOUNDS.items():
            write_wav(os.path.join(outdir, f'{name}.wav'), normalize(fn(rng, style), .8))
