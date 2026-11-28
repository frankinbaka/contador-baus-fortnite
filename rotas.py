"""
Rotas de baús: dado um ponto de pouso e um tempo, monta a rota que abre o
máximo de baús (problema de "orientação": juntar o máximo de prêmio dentro
de um limite de tempo).

Unidades: as coordenadas vêm do mapa do fortnite.gg (1 unidade ≈ 11,7 m).
"""
import json
import math
import os

import numpy as np


class Mapa:
    def __init__(self, pasta):
        self.pasta = pasta
        with open(os.path.join(pasta, "dados_mapa.json"), encoding="utf-8") as f:
            d = json.load(f)
        self.dados = d
        self.versao = d.get("versao", "?")
        self.locais = d["locais"]
        self.imagem = os.path.join(pasta, d["imagem"])
        self.px, self.py = d["pixel_x"], d["pixel_y"]
        pts = [(x, y, 1.0) for x, y in d["baus"]] + [(x, y, 1.0) for x, y in d["baus_raros"]]
        self.pontos = np.array(pts, dtype=float)

    def para_pixel(self, x, y):
        a, b, c = self.px
        d, e, f = self.py
        return a * x + b * y + c, d * x + e * y + f

    def de_pixel(self, X, Y):
        a, b, c = self.px
        d, e, f = self.py
        m = np.array([[a, b], [d, e]])
        x, y = np.linalg.solve(m, [X - c, Y - f])
        return float(x), float(y)

    def nome_perto(self, x, y):
        """Nome do lugar mais perto (região grande ou ponto marcante)."""
        melhor, dist = None, 1e9
        for l in self.locais:
            dd = math.hypot(l["x"] - x, l["y"] - y)
            # regiões grandes "puxam" de mais longe que os pontos marcantes
            peso = dd if l["tipo"] == "poi" else dd * 1.6
            if peso < dist:
                melhor, dist = l, peso
        dd = math.hypot(melhor["x"] - x, melhor["y"] - y)
        nome = melhor["nome"].title().replace("'S", "'s")
        if dd < 6:
            return nome
        direcao = direcao_cardeal(x - melhor["x"], y - melhor["y"])
        return f"{direcao} de {nome}"


def direcao_cardeal(dx, dy):
    # no mapa, y cresce para o SUL
    ang = math.degrees(math.atan2(-dy, dx)) % 360
    nomes = ["Leste", "Nordeste", "Norte", "Noroeste", "Oeste", "Sudoeste", "Sul", "Sudeste"]
    return nomes[int((ang + 22.5) // 45) % 8]


class Parada:
    def __init__(self, x, y, baus, extra_s, indices):
        self.x, self.y = x, y
        self.baus = baus          # quantos baús nesta parada
        self.extra_s = extra_s    # tempo andando entre os baús da parada
        self.indices = indices
        self.nome = ""


def agrupar(pontos, raio=1.3):
    """Junta baús próximos (mesma casa/prédio) numa parada só."""
    n = len(pontos)
    pai = list(range(n))

    def raiz(i):
        while pai[i] != i:
            pai[i] = pai[pai[i]]
            i = pai[i]
        return i

    xy = pontos[:, :2]
    for i in range(n):
        d = np.hypot(*(xy[i + 1:] - xy[i]).T)
        for j in np.nonzero(d < raio)[0]:
            a, b = raiz(i), raiz(i + 1 + j)
            if a != b:
                pai[a] = b
    grupos = {}
    for i in range(n):
        grupos.setdefault(raiz(i), []).append(i)
    return list(grupos.values())


def comprimento_mst(xy):
    """Caminho aproximado para passar por todos os pontos de um grupo."""
    n = len(xy)
    if n < 2:
        return 0.0
    dentro = [0]
    fora = set(range(1, n))
    total = 0.0
    melhor = {j: math.hypot(*(xy[j] - xy[0])) for j in fora}
    while fora:
        j = min(fora, key=melhor.get)
        total += melhor[j]
        fora.remove(j)
        dentro.append(j)
        for k in fora:
            d = math.hypot(*(xy[k] - xy[j]))
            if d < melhor[k]:
                melhor[k] = d
    return total


class Planejador:
    def __init__(self, mapa, metros_por_unidade=11.7, velocidade_m_s=6.0, segundos_por_bau=7.0):
        self.mapa = mapa
        self.vel = velocidade_m_s / metros_por_unidade      # unidades por segundo
        self.seg_bau = segundos_por_bau
        self.paradas = []
        for g in agrupar(mapa.pontos):
            xy = mapa.pontos[g, :2]
            cx, cy = xy.mean(axis=0)
            extra = comprimento_mst(xy) / self.vel
            p = Parada(float(cx), float(cy), len(g), extra, g)
            p.nome = mapa.nome_perto(cx, cy)
            self.paradas.append(p)
        self.P = np.array([[p.x, p.y] for p in self.paradas])
        self.D = np.hypot(self.P[:, None, 0] - self.P[None, :, 0], self.P[:, None, 1] - self.P[None, :, 1]) / self.vel
        self.ganho = np.array([p.baus for p in self.paradas], dtype=float)
        self.custo_parada = np.array([p.baus * self.seg_bau + p.extra_s for p in self.paradas])

    # ---- tempo de uma rota (lista de índices de paradas), saindo do ponto de pouso
    def _tempo(self, inicio_d, rota):
        if not rota:
            return 0.0
        t = inicio_d[rota[0]]
        for a, b in zip(rota, rota[1:]):
            t += self.D[a, b]
        return t + self.custo_parada[rota].sum()

    def rota(self, x, y, minutos=8.0, evitar=()):
        """Melhor rota saindo de (x, y). Retorna lista de paradas na ordem."""
        limite = minutos * 60
        ini = np.hypot(self.P[:, 0] - x, self.P[:, 1] - y) / self.vel
        livres = set(range(len(self.paradas))) - set(evitar)
        rota = []
        tempo = 0.0

        def custo_inserir(k, pos):
            # tempo extra para colocar a parada k na posição pos
            if not rota:
                return ini[k] + self.custo_parada[k]
            if pos == 0:
                return ini[k] + self.D[k, rota[0]] - ini[rota[0]] + self.custo_parada[k]
            a = rota[pos - 1]
            if pos == len(rota):
                return self.D[a, k] + self.custo_parada[k]
            b = rota[pos]
            return self.D[a, k] + self.D[k, b] - self.D[a, b] + self.custo_parada[k]

        while True:
            melhor = None
            sobra = limite - tempo
            # só olha paradas que dá para alcançar
            cand = [k for k in livres if ini[k] < limite]
            for k in cand:
                for pos in range(len(rota) + 1):
                    c = custo_inserir(k, pos)
                    if c > sobra:
                        continue
                    nota = self.ganho[k] / (c + 1.0)
                    if melhor is None or nota > melhor[0]:
                        melhor = (nota, k, pos, c)
            if melhor is None:
                break
            _, k, pos, c = melhor
            rota.insert(pos, k)
            livres.discard(k)
            tempo += c
            rota = self._dois_opt(ini, rota)
            tempo = self._tempo(ini, rota)
        return [self.paradas[k] for k in rota], tempo

    def _dois_opt(self, ini, rota):
        """Desfaz cruzamentos no caminho (encurta o tempo andando)."""
        melhorou = True
        while melhorou and len(rota) > 2:
            melhorou = False
            base = self._tempo(ini, rota)
            for i in range(len(rota) - 1):
                for j in range(i + 1, len(rota)):
                    nova = rota[:i] + rota[i:j + 1][::-1] + rota[j + 1:]
                    t = self._tempo(ini, nova)
                    if t < base - 1e-6:
                        rota, base, melhorou = nova, t, True
        return rota

    def melhores_pousos(self, minutos=8.0, n=5):
        """Testa pousar em cada região e devolve as que rendem mais baús."""
        res = []
        for l in self.mapa.locais:
            paradas, t = self.rota(l["x"], l["y"], minutos)
            res.append((sum(p.baus for p in paradas), l["nome"], t))
        return sorted(res, reverse=True)[:n]



class Etapa:
    """Paradas seguidas no mesmo lugar viram uma etapa ("Cursed Cavern: 14 baús")."""

    def __init__(self, nome, paradas):
        self.nome = nome
        self.paradas = paradas
        self.baus = sum(p.baus for p in paradas)
        self.x = sum(p.x * p.baus for p in paradas) / self.baus
        self.y = sum(p.y * p.baus for p in paradas) / self.baus


def juntar_etapas(paradas):
    etapas = []
    for p in paradas:
        if etapas and etapas[-1][0] == p.nome:
            etapas[-1][1].append(p)
        else:
            etapas.append((p.nome, [p]))
    return [Etapa(n, ps) for n, ps in etapas]


class RotaAtiva:
    """Onde você está na rota. Avança sozinho quando abre os baús da etapa."""

    def __init__(self, etapas, inicio_xy, minutos):
        self.etapas = etapas
        self.inicio = inicio_xy
        self.minutos = minutos
        self.i = 0
        self.feitos = 0

    @property
    def atual(self):
        return self.etapas[self.i] if self.i < len(self.etapas) else None

    @property
    def total(self):
        return sum(e.baus for e in self.etapas)

    def bau(self):
        if self.atual is None:
            return
        self.feitos += 1
        if self.feitos >= self.atual.baus:
            self.proxima()

    def proxima(self):
        if self.i < len(self.etapas):
            self.i += 1
            self.feitos = 0

    def anterior(self):
        if self.i > 0:
            self.i -= 1
            self.feitos = 0

    def reiniciar(self):
        self.i = 0
        self.feitos = 0

    def textos(self):
        if self.atual is None:
            return "ROTA COMPLETA ✔", ""
        a = self.atual
        l1 = f"ROTA {self.i + 1}/{len(self.etapas)}: {a.nome}  {self.feitos}/{a.baus}"
        prox = self.etapas[self.i + 1] if self.i + 1 < len(self.etapas) else None
        l2 = f"depois: {prox.nome} ({prox.baus})" if prox else "última etapa"
        return l1, l2


def desenhar_rota(mapa, etapas, atual=0, inicio=None, tamanho=None, recorte=True, base=None):
    """Imagem (PIL) do mapa com a rota. recorte=True corta em volta da rota."""
    from PIL import Image, ImageDraw
    img = (base or Image.open(mapa.imagem)).convert("RGB")
    d = ImageDraw.Draw(img)
    pts = []
    if inicio:
        pts.append(mapa.para_pixel(*inicio))
    pts += [mapa.para_pixel(e.x, e.y) for e in etapas]
    # caminho detalhado (passa por todas as paradas)
    det = ([mapa.para_pixel(*inicio)] if inicio else []) + \
          [mapa.para_pixel(p.x, p.y) for e in etapas for p in e.paradas]
    if len(det) > 1:
        d.line(det, fill=(255, 60, 60), width=3)
    for k, e in enumerate(etapas):
        X, Y = mapa.para_pixel(e.x, e.y)
        cor = (120, 120, 120) if k < atual else ((255, 211, 77) if k == atual else (255, 255, 255))
        r = 9 if k == atual else 7
        d.ellipse((X - r, Y - r, X + r, Y + r), fill=cor, outline=(0, 0, 0), width=2)
        d.text((X - 3, Y - 6), str(k + 1), fill=(0, 0, 0))
    if inicio:
        X, Y = mapa.para_pixel(*inicio)
        d.rectangle((X - 6, Y - 6, X + 6, Y + 6), fill=(60, 220, 90), outline=(0, 0, 0), width=2)
    if recorte and pts:
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        m = 40
        caixa = (max(0, min(xs) - m), max(0, min(ys) - m), min(img.width, max(xs) + m), min(img.height, max(ys) + m))
        # deixa quadrado para caber bem no canto da tela
        w, h = caixa[2] - caixa[0], caixa[3] - caixa[1]
        lado = max(w, h, 160)
        cx, cy = (caixa[0] + caixa[2]) / 2, (caixa[1] + caixa[3]) / 2
        caixa = (int(max(0, cx - lado / 2)), int(max(0, cy - lado / 2)),
                 int(min(img.width, cx + lado / 2)), int(min(img.height, cy + lado / 2)))
        img = img.crop(caixa)
    if tamanho:
        img.thumbnail((tamanho, tamanho))
    return img
