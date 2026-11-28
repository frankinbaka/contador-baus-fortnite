"""
Contador de Baús e Tesouros - Fortnite
Roda em segundo plano (ícone na bandeja), conta baús e tesouros por partida,
mostra um contador por cima do jogo e guarda o histórico com o total.

Como ele detecta (só olhando a imagem da tela, sem mexer no jogo):
  - BAÚ      -> o aviso "+600 EXP / BAÚ" que aparece quando o baú abre
  - TESOURO  -> o selo "VOCÊ ENCONTROU ..."
  - FIM      -> a aba "RESUMO DA PARTIDA" da tela de morte/vitória;
                ali ele também conta os tesouros de "TESOURO ENCONTRADO"

Atalhos globais (funcionam com o jogo aberto):
  F8 / F7        -> +1 / -1 baú
  F6 / Ctrl+F6   -> +1 / -1 tesouro
  F9             -> finalizar partida
  Ctrl+Shift+B / T / F -> print para criar um modelo novo de baú / tesouro / fim
"""
import ctypes
import json
import os
import queue
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox

CONGELADO = getattr(sys, "frozen", False)  # rodando como .exe?
# dados, config e modelos que você criar ficam ao lado do .exe (ou do .py)
PASTA = os.path.dirname(os.path.abspath(sys.executable if CONGELADO else __file__))
# modelos que já vêm prontos dentro do .exe
PASTA_PACOTE = getattr(sys, "_MEIPASS", PASTA)
ARQ_DADOS = os.path.join(PASTA, "dados_baus.json")
ARQ_CONFIG = os.path.join(PASTA, "config.json")
PASTA_MODELOS = os.path.join(PASTA, "modelos")
PASTAS_MODELOS_LEITURA = list(dict.fromkeys([os.path.join(PASTA_PACOTE, "modelos"), PASTA_MODELOS]))
TIPOS = ("bau", "tesouro", "fim")

CANTOS = {
    "esquerda_meio": "Esquerda, meio",
    "superior_esquerdo": "Superior esquerdo",
    "inferior_esquerdo": "Inferior esquerdo (acima da vida)",
    "superior_centro": "Topo, centro",
    "superior_direito": "Direita, abaixo do mapa",
    "inferior_direito": "Inferior direito",
}

CONFIG_PADRAO = {
    "atalho_mais_bau": "f8",
    "atalho_menos_bau": "f7",
    "atalho_mais_tesouro": "f6",
    "atalho_menos_tesouro": "ctrl+f6",
    "atalho_finalizar": "f9",
    "atalho_modelo_bau": "ctrl+shift+b",
    "atalho_modelo_tesouro": "ctrl+shift+t",
    "atalho_modelo_fim": "ctrl+shift+f",
    "deteccao_automatica": True,
    "so_com_fortnite_em_foco": True,
    "intervalo_segundos": 0.15,
    "limiar_padrao": 0.80,          # para modelos novos que você recortar
    "margem_padrao_px": 80,
    "sumir_antes_de_contar_de_novo": 0.8,  # o aviso precisa sumir por X s
    "olhadas_seguidas": 2,          # o aviso precisa aparecer em N olhadas seguidas
    "salvar_print_de_cada_contagem": True,  # pasta "conferir" (guarda as últimas 200)
    "som_ao_contar": True,
    "overlay_ativo": True,
    "overlay_canto": "esquerda_meio",
    "overlay_tamanho_fonte": 16,
    "overlay_opacidade": 0.85,
    "overlay_so_com_fortnite": True,
    "atalho_proxima_etapa": "f10",
    "atalho_etapa_anterior": "shift+f10",
    "rota_minutos": 8,
    "rota_velocidade_m_s": 6.0,       # andando/correndo entre os baús
    "rota_segundos_por_bau": 7,       # abrir + pegar os itens
    "overlay_mapa_rota": True,        # mapinha da rota no contador do jogo
    "overlay_tamanho_mapa": 200,
}


def agora():
    return datetime.now().strftime("%d/%m/%Y %H:%M")


# ------------------------------------------------------------------ dados
class Contador:
    """Partidas salvas + partida atual. Sem interface, fácil de testar."""

    def __init__(self, arquivo=ARQ_DADOS):
        self.arquivo = arquivo
        self.partidas = []
        self.baus = 0
        self.tesouros = 0
        self.inicio = None
        self.carregar()

    def carregar(self):
        if os.path.exists(self.arquivo):
            with open(self.arquivo, encoding="utf-8") as f:
                d = json.load(f)
            self.partidas = d.get("partidas", [])
            for p in self.partidas:
                p.setdefault("tesouros", 0)
            self.baus = d.get("atual", 0)
            self.tesouros = d.get("tesouros_atual", 0)
            self.inicio = d.get("inicio_atual")

    def salvar(self):
        tmp = self.arquivo + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"partidas": self.partidas, "atual": self.baus,
                       "tesouros_atual": self.tesouros, "inicio_atual": self.inicio},
                      f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.arquivo)

    def _comecou(self):
        if self.inicio is None:
            self.inicio = agora()

    def mais_bau(self):
        self._comecou()
        self.baus += 1
        self.salvar()

    def menos_bau(self):
        if self.baus > 0:
            self.baus -= 1
            self.salvar()

    def mais_tesouro(self):
        self._comecou()
        self.tesouros += 1
        self.salvar()

    def menos_tesouro(self):
        if self.tesouros > 0:
            self.tesouros -= 1
            self.salvar()

    def finalizar(self, motivo="manual", tesouros_tela_final=None):
        """Fecha a partida. Se a tela final mostrou quantos tesouros, usa o maior valor.
        Retorna False se não havia nada para salvar."""
        tes = self.tesouros
        if tesouros_tela_final is not None:
            tes = max(tes, tesouros_tela_final)
        if self.baus == 0 and tes == 0:
            return False
        self.partidas.append({
            "numero": len(self.partidas) + 1,
            "baus": self.baus,
            "tesouros": tes,
            "inicio": self.inicio,
            "fim": agora(),
            "fim_ts": time.time(),
            "finalizada_por": motivo,
        })
        self.baus = self.tesouros = 0
        self.inicio = None
        self.salvar()
        return True

    def tesouros_tela_final(self, n, janela_s=180):
        """O RESUMO DA PARTIDA mostrou n tesouros. Se a partida acabou de ser salva
        (pela tela de eliminação), corrige ela; senão, fecha a partida atual."""
        if self.baus == 0 and self.tesouros == 0 and self.partidas \
                and time.time() - self.partidas[-1].get("fim_ts", 0) < janela_s:
            p = self.partidas[-1]
            if n > p["tesouros"]:
                p["tesouros"] = n
                self.salvar()
            return True
        return self.finalizar("automático", n)

    def apagar_partida(self, numero):
        self.partidas = [p for p in self.partidas if p["numero"] != numero]
        for i, p in enumerate(self.partidas, 1):
            p["numero"] = i
        self.salvar()

    @property
    def total_baus(self):
        return sum(p["baus"] for p in self.partidas) + self.baus

    @property
    def total_tesouros(self):
        return sum(p["tesouros"] for p in self.partidas) + self.tesouros

    @property
    def media_baus(self):
        return sum(p["baus"] for p in self.partidas) / len(self.partidas) if self.partidas else 0


def carregar_config():
    cfg = dict(CONFIG_PADRAO)
    if os.path.exists(ARQ_CONFIG):
        with open(ARQ_CONFIG, encoding="utf-8") as f:
            salvo = json.load(f)
        cfg.update({k: v for k, v in salvo.items() if k in CONFIG_PADRAO})
    salvar_config(cfg)
    return cfg


def salvar_config(cfg):
    with open(ARQ_CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def fortnite_em_foco():
    user32 = ctypes.windll.user32
    buf = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(user32.GetForegroundWindow(), buf, 256)
    return "fortnite" in buf.value.lower()


# --------------------------------------------------------------- detecção
def mascara_branca(bgr):
    """Deixa só o texto branco (o aviso de EXP é branco com contorno roxo)."""
    import cv2
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (0, 0, 190), (180, 70, 255))


def mascara_amarela(bgr):
    """Deixa só o texto amarelo (em algumas contas o "BAÚ" do aviso vem amarelo)."""
    import cv2
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    return cv2.inRange(hsv, (15, 110, 170), (38, 255, 255))


def preparar(bgr, metodo):
    import cv2
    if metodo == "branco":
        return mascara_branca(bgr)
    if metodo == "amarelo":
        return mascara_amarela(bgr)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)


def contar_tesouros_tela_final(tela_bgr):
    """Conta os quadros dourados em 'TESOURO ENCONTRADO' na tela de fim de partida."""
    import cv2
    h, w = tela_bgr.shape[:2]
    e = h / 1080
    hsv = cv2.cvtColor(tela_bgr, cv2.COLOR_BGR2HSV)
    ouro = cv2.inRange(hsv, (12, 90, 170), (40, 255, 255))
    n = 0
    for k in range(10):
        x0, y0 = int((108 + 130 * k) * e), int(250 * e)
        x1, y1 = x0 + int(108 * e), y0 + int(106 * e)
        if x1 > w:
            break
        ring = ouro[y0:y1, x0:x1].copy()
        b = max(1, int(12 * e))
        ring[b:-b, b:-b] = 0
        area_borda = ring.size - (ring.shape[0] - 2 * b) * (ring.shape[1] - 2 * b)
        if ring.sum() / 255 / area_borda > 0.10:
            n += 1
        else:
            break
    return n


class Detector(threading.Thread):
    def __init__(self, cfg, fila):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.fila = fila
        self.ativo = cfg["deteccao_automatica"]
        self.modelos = {t: [] for t in TIPOS}
        self.recarregar = True
        self._cache = {}          # modelos redimensionados para a resolução atual
        self.visto_em = {t: -99.0 for t in TIPOS}
        self.seguidos = {t: 0 for t in TIPOS}

    def carregar_modelos(self):
        import cv2
        for tipo in TIPOS:
            lista = []
            arquivos = []
            for base in PASTAS_MODELOS_LEITURA:
                pasta = os.path.join(base, tipo)
                if os.path.isdir(pasta):
                    arquivos += [(pasta, n) for n in sorted(os.listdir(pasta))]
            for pasta, nome in arquivos:
                # *.conf.png = imagem de confirmação usada por outro modelo
                if not nome.lower().endswith(".png") or nome.lower().endswith(".conf.png"):
                    continue
                img = cv2.imread(os.path.join(pasta, nome))
                if img is None:
                    continue
                meta = {}
                arq = os.path.join(pasta, nome[:-4] + ".json")
                if os.path.exists(arq):
                    with open(arq, encoding="utf-8") as f:
                        meta = json.load(f)
                meta.setdefault("metodo", "cinza")
                meta.setdefault("limiar", self.cfg["limiar_padrao"])
                meta.setdefault("margem", self.cfg["margem_padrao_px"])
                conf = meta.get("confirmar")
                if conf:
                    conf["img"] = cv2.imread(os.path.join(pasta, conf["arquivo"]))
                    if conf["img"] is None:
                        meta.pop("confirmar")
                lista.append((img, meta))
            self.modelos[tipo] = lista
        self._cache.clear()
        self.recarregar = False

    def _modelo_na_tela(self, i_tipo, img, meta, w, h):
        """Ajusta tamanho/posição do modelo se a sua tela tiver outra resolução."""
        import cv2
        chave = (i_tipo, w, h)
        if chave not in self._cache:
            W, H = meta.get("largura_tela"), meta.get("altura_tela")
            e = h / H if H else 1.0
            t = img if abs(e - 1) < 0.01 else cv2.resize(img, None, fx=e, fy=e, interpolation=cv2.INTER_AREA)
            pos = None
            if W and H and "x" in meta:
                m = int(meta["margem"] * e)
                my = int(meta.get("margem_y", meta["margem"]) * e)
                pos = (int(meta["x"] * w / W), int(meta["y"] * h / H), m, my)
            conf = None
            c = meta.get("confirmar")
            if c:
                ci = c["img"] if abs(e - 1) < 0.01 else cv2.resize(c["img"], None, fx=e, fy=e, interpolation=cv2.INTER_AREA)
                conf = (preparar(ci, c.get("metodo", "cinza")), c.get("metodo", "cinza"),
                        int(c["dx"] * e), int(c["dy"] * e), int(c["folga_x"] * e), int(c["folga_y"] * e), c["limiar"])
            self._cache[chave] = (preparar(t, meta["metodo"]), pos, conf)
        return self._cache[chave]

    def aparece(self, tela_bgr, tipo):
        import cv2
        h, w = tela_bgr.shape[:2]
        for i, (img, meta) in enumerate(self.modelos[tipo]):
            t, pos, conf = self._modelo_na_tela((tipo, i), img, meta, w, h)
            th, tw = t.shape[:2]
            ox = oy = 0
            if pos:
                x, y, m, my = pos
                ox, oy = max(0, x - m), max(0, y - my)
                area = tela_bgr[oy:min(h, y + th + my), ox:min(w, x + tw + m)]
            else:
                area = tela_bgr
            if area.shape[0] < th or area.shape[1] < tw:
                continue
            r = cv2.matchTemplate(preparar(area, meta["metodo"]), t, cv2.TM_CCOEFF_NORMED)
            _, nota, _, (mx, my_) = cv2.minMaxLoc(r)
            if nota < meta["limiar"]:
                continue
            if conf:
                # confirma com uma 2ª imagem numa posição fixa em relação à 1ª (ex.: "EXP" acima de "BAÚ")
                ct, cmet, dx, dy, fx, fy, clim = conf
                cx, cy = ox + mx + dx, oy + my_ + dy
                ch, cw = ct.shape[:2]
                jan = tela_bgr[max(0, cy - fy):min(h, cy + ch + fy), max(0, cx - fx):min(w, cx + cw + fx)]
                if jan.shape[0] < ch or jan.shape[1] < cw:
                    continue
                if cv2.matchTemplate(preparar(jan, cmet), ct, cv2.TM_CCOEFF_NORMED).max() < clim:
                    continue
            return meta
        return None

    def analisar(self, tela_bgr, t):
        """Retorna os eventos novos ('bau', 'tesouro', 'fim') deste quadro."""
        eventos = []
        sumir = {"bau": self.cfg["sumir_antes_de_contar_de_novo"],
                 "tesouro": self.cfg["sumir_antes_de_contar_de_novo"], "fim": 20.0}
        self.visivel_agora = {}
        for tipo in TIPOS:
            achado = self.aparece(tela_bgr, tipo) if self.modelos[tipo] else None
            self.visivel_agora[tipo] = achado
            v = achado is not None
            self.seguidos[tipo] = self.seguidos[tipo] + 1 if v else 0
            # precisa aparecer em N olhadas seguidas (coisas que só passam pela tela não contam)
            if self.seguidos[tipo] >= self.cfg["olhadas_seguidas"]:
                # só conta quando o aviso APARECE (estava sumido há um tempinho)
                if t - self.visto_em[tipo] > sumir[tipo]:
                    eventos.append(tipo)
                self.visto_em[tipo] = t
        return eventos

    def salvar_print(self, tela, ev):
        """Guarda uma foto pequena de cada contagem, pra conferir se houve erro."""
        import cv2
        try:
            pasta = os.path.join(PASTA, "conferir")
            os.makedirs(pasta, exist_ok=True)
            nome = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + f"_{ev}.jpg"
            cv2.imwrite(os.path.join(pasta, nome), cv2.resize(tela, (960, 540)), [cv2.IMWRITE_JPEG_QUALITY, 80])
            antigos = sorted(os.listdir(pasta))
            for a in antigos[:-200]:
                os.remove(os.path.join(pasta, a))
        except OSError:
            pass

    def run(self):
        import mss
        import numpy as np
        with mss.MSS() if hasattr(mss, "MSS") else mss.mss() as sct:
            mon = sct.monitors[1]
            grab = lambda: np.asarray(sct.grab(mon))[:, :, :3]
            while True:
                time.sleep(self.cfg["intervalo_segundos"])
                if self.recarregar:
                    self.carregar_modelos()
                if not self.ativo:
                    continue
                if self.cfg["so_com_fortnite_em_foco"] and not fortnite_em_foco():
                    continue
                tela = grab()
                for ev in self.processar(tela, time.time()):
                    if ev in ("bau", "tesouro") and self.cfg["salvar_print_de_cada_contagem"]:
                        self.salvar_print(tela, ev)
                    self.fila.put(ev)

    tesouros_fim_avisados = 0

    def processar(self, tela, t):
        """Eventos do quadro + contagem de tesouros enquanto o RESUMO DA PARTIDA está na tela.
        O fim pode vir primeiro pela tela de eliminação e o resumo aparecer depois."""
        eventos = []
        for ev in self.analisar(tela, t):
            if ev == "fim":
                self.tesouros_fim_avisados = 0
                eventos.append(("fim", None))
            else:
                eventos.append(ev)
        achado = self.visivel_agora.get("fim")
        if achado and achado.get("contar_tesouros") and self.seguidos["fim"] >= self.cfg["olhadas_seguidas"]:
            n = contar_tesouros_tela_final(tela)
            if n > self.tesouros_fim_avisados:
                self.tesouros_fim_avisados = n
                eventos.append(("tesouros_fim", n))
        return eventos


# ------------------------------------------------------- contador na tela
class Overlay:
    """Janelinha sem borda, sempre por cima e que deixa o clique passar."""

    def __init__(self, root, cfg):
        self.cfg = cfg
        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", cfg["overlay_opacidade"])
        self.win.configure(bg="#120d24")
        fs = cfg["overlay_tamanho_fonte"]
        caixa = tk.Frame(self.win, bg="#120d24", padx=12, pady=6,
                         highlightthickness=2, highlightbackground="#ffd34d")
        caixa.pack()
        self.lbl_bau = tk.Label(caixa, bg="#120d24", fg="#ffd34d", font=("Segoe UI", fs, "bold"), anchor="w")
        self.lbl_tes = tk.Label(caixa, bg="#120d24", fg="#6fe3ff", font=("Segoe UI", fs, "bold"), anchor="w")
        self.lbl_bau.pack(fill="x")
        self.lbl_tes.pack(fill="x")
        fr = max(9, fs - 5)
        self.lbl_rota1 = tk.Label(caixa, bg="#120d24", fg="white", font=("Segoe UI", fr, "bold"), anchor="w")
        self.lbl_rota2 = tk.Label(caixa, bg="#120d24", fg="#b9b0d9", font=("Segoe UI", fr - 1), anchor="w")
        self.lbl_mapa = tk.Label(caixa, bg="#120d24", bd=0)
        self._rota_visivel = False
        self._mapa_ref = None
        self.mostrando = True
        self.win.after(50, self._clique_passa)

    def atualizar_rota(self, linha1, linha2, imagem_pil=None):
        """Mostra a etapa atual da rota (ou esconde, se linha1 for None)."""
        if linha1 is None:
            if self._rota_visivel:
                for w in (self.lbl_rota1, self.lbl_rota2, self.lbl_mapa):
                    w.pack_forget()
                self._rota_visivel = False
            self.posicionar()
            return
        if not self._rota_visivel:
            self.lbl_rota1.pack(fill="x", pady=(6, 0))
            self.lbl_rota2.pack(fill="x")
            self._rota_visivel = True
        self.lbl_rota1.config(text=linha1)
        self.lbl_rota2.config(text=linha2)
        if imagem_pil is not None:
            if getattr(self, "_mapa_pil", None) is not imagem_pil:
                from PIL import ImageTk
                self._mapa_pil = imagem_pil
                self._mapa_ref = ImageTk.PhotoImage(imagem_pil)
                self.lbl_mapa.config(image=self._mapa_ref)
            self.lbl_mapa.pack(pady=(4, 0))
        else:
            self.lbl_mapa.pack_forget()
        self.posicionar()

    def _clique_passa(self):
        u = ctypes.windll.user32
        hwnd = u.GetParent(self.win.winfo_id()) or self.win.winfo_id()
        GWL_EXSTYLE = -20
        estilo = u.GetWindowLongW(hwnd, GWL_EXSTYLE)
        # LAYERED | TRANSPARENT (clique atravessa) | TOOLWINDOW (sem barra de tarefas) | NOACTIVATE
        u.SetWindowLongW(hwnd, GWL_EXSTYLE, estilo | 0x80000 | 0x20 | 0x80 | 0x08000000)

    def atualizar(self, baus, tesouros):
        self.lbl_bau.config(text=f"BAÚS   {baus}")
        self.lbl_tes.config(text=f"TESOUROS   {tesouros}")
        self.posicionar()

    def posicionar(self):
        self.win.update_idletasks()
        sw, sh = self.win.winfo_screenwidth(), self.win.winfo_screenheight()
        w, h = self.win.winfo_reqwidth(), self.win.winfo_reqheight()
        m = 20
        x, y = {
            "superior_esquerdo": (m, int(sh * 0.09)),
            "esquerda_meio": (m, int(sh * 0.38)),
            "inferior_esquerdo": (m, int(sh * 0.86) - h),
            "superior_centro": ((sw - w) // 2, int(sh * 0.08)),
            "superior_direito": (sw - w - m, int(sh * 0.29)),
            "inferior_direito": (sw - w - m, int(sh * 0.70)),
        }.get(self.cfg["overlay_canto"], (m, int(sh * 0.38)))
        self.win.geometry(f"+{x}+{y}")

    def mostrar(self, sim):
        if sim != self.mostrando:
            (self.win.deiconify if sim else self.win.withdraw)()
            if sim:
                self.win.attributes("-topmost", True)
            self.mostrando = sim


# ------------------------------------------------------------- interface
BG, BG2, ROXO, OURO, AZUL = "#1b1530", "#2a2245", "#3b2f63", "#ffd34d", "#6fe3ff"


class App:
    icone = None

    def __init__(self):
        self.cfg = carregar_config()
        self.dados = Contador()
        self.fila = queue.Queue()
        self.detector = Detector(self.cfg, self.fila)

        self.root = tk.Tk()
        self.root.title("Contador de Baús")
        self.root.geometry("440x600")
        self.root.protocol("WM_DELETE_WINDOW", self.root.withdraw)
        self.rota = None            # rotas.RotaAtiva
        self._planejador = None
        self.montar_tela()
        self.overlay = Overlay(self.root, self.cfg)

        self.registrar_atalhos()
        self.criar_icone_bandeja()
        self.detector.start()
        self.atualizar()
        self.root.after(100, self.ler_fila)
        self.root.after(500, self.vigiar_overlay)

    # ---- montagem
    def montar_tela(self):
        r = self.root
        r.configure(bg=BG)
        st = ttk.Style(r)
        st.theme_use("clam")
        st.configure("Treeview", background=BG2, fieldbackground=BG2, foreground="white", rowheight=24)
        st.configure("Treeview.Heading", background=ROXO, foreground="white")

        tk.Label(r, text="PARTIDA ATUAL", bg=BG, fg="#c9b8ff", font=("Segoe UI", 10, "bold")).pack(pady=(12, 0))
        topo = tk.Frame(r, bg=BG)
        topo.pack()
        self.lbl_baus = self._bloco(topo, "baús", OURO)
        self.lbl_tes = self._bloco(topo, "tesouros", AZUL)

        bt = tk.Frame(r, bg=BG)
        bt.pack(pady=4)
        for txt, cmd in (("−1 baú", self.dados.menos_bau), ("+1 baú", self.dados.mais_bau),
                         ("−1 tes.", self.dados.menos_tesouro), ("+1 tes.", self.dados.mais_tesouro)):
            self._botao(bt, txt, lambda c=cmd: (c(), self.atualizar())).pack(side="left", padx=3)
        bt2 = tk.Frame(r, bg=BG)
        bt2.pack(pady=(2, 6))
        self._botao(bt2, "Finalizar partida (F9)", self.finalizar).pack(side="left", padx=3)
        tk.Button(bt2, text="🗺  Rotas de baús", command=self.abrir_rotas, bg=OURO, fg="#1b1530", relief="flat",
                  activebackground="#ffe58a", font=("Segoe UI", 9, "bold"), padx=8, pady=3).pack(side="left", padx=3)

        self.lbl_total = tk.Label(r, bg=BG, fg="white", font=("Segoe UI", 11, "bold"))
        self.lbl_total.pack(pady=(4, 2))

        cols = (("n", "Partida", 70), ("baus", "Baús", 60), ("tes", "Tesouros", 75), ("fim", "Terminou em", 150))
        self.tabela = ttk.Treeview(r, columns=[c[0] for c in cols], show="headings", height=9)
        for c, txt, w in cols:
            self.tabela.heading(c, text=txt)
            self.tabela.column(c, width=w, anchor="center")
        self.tabela.pack(fill="both", expand=True, padx=12)
        self.tabela.bind("<Delete>", self.apagar_selecionada)

        op = tk.Frame(r, bg=BG)
        op.pack(fill="x", padx=12, pady=(8, 0))
        self.var_auto = tk.BooleanVar(value=self.detector.ativo)
        self._check(op, "Detecção automática", self.var_auto, self.alternar_auto).pack(side="left")
        self.var_overlay = tk.BooleanVar(value=self.cfg["overlay_ativo"])
        self._check(op, "Mostrar no jogo", self.var_overlay, self.alternar_overlay).pack(side="left", padx=8)

        op2 = tk.Frame(r, bg=BG)
        op2.pack(fill="x", padx=12, pady=4)
        tk.Label(op2, text="Canto:", bg=BG, fg="white").pack(side="left")
        self.var_canto = tk.StringVar(value=CANTOS.get(self.cfg["overlay_canto"], CANTOS["esquerda_meio"]))
        cb = ttk.Combobox(op2, textvariable=self.var_canto, values=list(CANTOS.values()), state="readonly", width=30)
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", self.mudar_canto)

        self.lbl_modelos = tk.Label(r, bg=BG, fg="#9a8cc9", font=("Segoe UI", 8))
        self.lbl_modelos.pack()
        tk.Label(r, text="F8/F7 baú ±1   F6/Ctrl+F6 tesouro ±1   F9 finalizar   Del apaga partida",
                 bg=BG, fg="#9a8cc9", font=("Segoe UI", 8)).pack(pady=(0, 8))

    def _bloco(self, pai, nome, cor):
        f = tk.Frame(pai, bg=BG)
        f.pack(side="left", padx=18)
        lbl = tk.Label(f, text="0", bg=BG, fg=cor, font=("Segoe UI", 44, "bold"))
        lbl.pack()
        tk.Label(f, text=nome, bg=BG, fg=cor, font=("Segoe UI", 10)).pack()
        return lbl

    def _botao(self, pai, txt, cmd):
        return tk.Button(pai, text=txt, command=cmd, bg=ROXO, fg="white", relief="flat",
                         activebackground="#5a4793", activeforeground="white", padx=8, pady=3)

    def _check(self, pai, txt, var, cmd):
        return tk.Checkbutton(pai, text=txt, variable=var, command=cmd, bg=BG, fg="white",
                              selectcolor=BG2, activebackground=BG, activeforeground="white")

    def atualizar(self):
        d = self.dados
        self.lbl_baus.config(text=str(d.baus))
        self.lbl_tes.config(text=str(d.tesouros))
        self.lbl_total.config(text=f"Total: {d.total_baus} baús  •  {d.total_tesouros} tesouros  •  "
                                   f"{len(d.partidas)} partidas  •  média {d.media_baus:.1f}")
        self.tabela.delete(*self.tabela.get_children())
        for p in reversed(d.partidas):
            self.tabela.insert("", "end", iid=str(p["numero"]),
                               values=(f"{p['numero']}ª", p["baus"], p["tesouros"], p["fim"] or ""))
        self.overlay.atualizar(d.baus, d.tesouros)
        self.atualizar_rota_overlay()
        n = {t: len(self.detector.modelos[t]) for t in TIPOS}
        self.lbl_modelos.config(text=f"modelos carregados: {n['bau']} baú • {n['tesouro']} tesouro • {n['fim']} fim")
        if self.icone:
            self.icone.title = f"Baús {d.baus} • Tesouros {d.tesouros} (total {d.total_baus})"

    # ---- rotas
    @property
    def planejador(self):
        if self._planejador is None:
            import rotas
            c = self.cfg
            self._planejador = rotas.Planejador(rotas.Mapa(os.path.join(PASTA_PACOTE, "mapa")),
                                                velocidade_m_s=c["rota_velocidade_m_s"],
                                                segundos_por_bau=c["rota_segundos_por_bau"])
        return self._planejador

    def abrir_rotas(self):
        JanelaRotas(self)

    def usar_rota(self, rota):
        self.rota = rota
        self._mapa_rota_chave = None
        self.atualizar()

    def atualizar_rota_overlay(self):
        if not self.rota:
            self.overlay.atualizar_rota(None, None)
            return
        l1, l2 = self.rota.textos()
        img = None
        if self.cfg["overlay_mapa_rota"]:
            chave = (id(self.rota), self.rota.i)
            if getattr(self, "_mapa_rota_chave", None) != chave:
                import rotas
                self._mapa_rota_img = rotas.desenhar_rota(self.planejador.mapa, self.rota.etapas, self.rota.i,
                                                          self.rota.inicio, self.cfg["overlay_tamanho_mapa"])
                self._mapa_rota_chave = chave
            img = self._mapa_rota_img
        self.overlay.atualizar_rota(l1, l2, img)

    def etapa(self, passo):
        if self.rota:
            (self.rota.proxima if passo > 0 else self.rota.anterior)()
            self.bip(1000 if passo > 0 else 700, 60)

    # ---- ações
    def finalizar(self, motivo="manual", tesouros_tela=None):
        if self.dados.finalizar(motivo, tesouros_tela):
            self.bip(600, 250)
        if self.rota:
            self.rota.reiniciar()   # próxima partida começa a rota do zero
        self.atualizar()

    def apagar_selecionada(self, _e=None):
        sel = self.tabela.selection()
        if sel and messagebox.askyesno("Apagar", f"Apagar a partida {sel[0]}ª?"):
            self.dados.apagar_partida(int(sel[0]))
            self.atualizar()

    def alternar_auto(self):
        self.detector.ativo = self.cfg["deteccao_automatica"] = self.var_auto.get()
        salvar_config(self.cfg)

    def alternar_overlay(self):
        self.cfg["overlay_ativo"] = self.var_overlay.get()
        salvar_config(self.cfg)

    def mudar_canto(self, _e=None):
        nome = self.var_canto.get()
        self.cfg["overlay_canto"] = next(k for k, v in CANTOS.items() if v == nome)
        salvar_config(self.cfg)
        self.overlay.posicionar()

    def vigiar_overlay(self):
        ver = self.cfg["overlay_ativo"] and (not self.cfg["overlay_so_com_fortnite"] or fortnite_em_foco())
        self.overlay.mostrar(ver)
        self.root.after(500, self.vigiar_overlay)

    def bip(self, freq, dur=80):
        if self.cfg["som_ao_contar"]:
            import winsound
            threading.Thread(target=winsound.Beep, args=(freq, dur), daemon=True).start()

    # ---- eventos (atalhos, detector, bandeja)
    def ler_fila(self):
        d = self.dados
        acoes = {
            "bau": lambda: (d.mais_bau(), self.rota and self.rota.bau(), self.bip(1200)),
            "proxima_etapa": lambda: self.etapa(+1),
            "etapa_anterior": lambda: self.etapa(-1),
            "tesouro": lambda: (d.mais_tesouro(), self.bip(1600, 150)),
            "menos_bau": d.menos_bau,
            "menos_tesouro": d.menos_tesouro,
            "finalizar": self.finalizar,
            "mostrar": self.mostrar,
            "rotas": lambda: (self.mostrar(), self.abrir_rotas()),
        }
        try:
            while True:
                ev = self.fila.get_nowait()
                if ev == "sair":
                    return self.sair()
                if isinstance(ev, tuple) and ev[0] == "fim":
                    self.finalizar("automático", ev[1])
                elif isinstance(ev, tuple) and ev[0] == "tesouros_fim":
                    d.tesouros_tela_final(ev[1])
                elif isinstance(ev, tuple) and ev[0] == "modelo":
                    self.janela_recorte(ev[1], ev[2])
                elif ev in acoes:
                    acoes[ev]()
                self.atualizar()
        except queue.Empty:
            pass
        self.root.after(100, self.ler_fila)

    def registrar_atalhos(self):
        import keyboard
        c, put = self.cfg, self.fila.put
        keyboard.add_hotkey(c["atalho_mais_bau"], lambda: put("bau"))
        keyboard.add_hotkey(c["atalho_menos_bau"], lambda: put("menos_bau"))
        keyboard.add_hotkey(c["atalho_mais_tesouro"], lambda: put("tesouro"))
        keyboard.add_hotkey(c["atalho_menos_tesouro"], lambda: put("menos_tesouro"))
        keyboard.add_hotkey(c["atalho_finalizar"], lambda: put("finalizar"))
        keyboard.add_hotkey(c["atalho_proxima_etapa"], lambda: put("proxima_etapa"))
        keyboard.add_hotkey(c["atalho_etapa_anterior"], lambda: put("etapa_anterior"))
        for tipo in TIPOS:
            keyboard.add_hotkey(c[f"atalho_modelo_{tipo}"], lambda t=tipo: self.tirar_print(t))

    def tirar_print(self, tipo):
        import mss
        import numpy as np
        with mss.MSS() if hasattr(mss, "MSS") else mss.mss() as sct:
            img = np.asarray(sct.grab(sct.monitors[1]))[:, :, :3].copy()
        self.bip(900, 60)
        self.fila.put(("modelo", tipo, img))

    def janela_recorte(self, tipo, img_bgr):
        import cv2
        from PIL import Image, ImageTk
        self.mostrar()
        h, w = img_bgr.shape[:2]
        esc = min(1100 / w, 650 / h, 1.0)
        mini = Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)).resize((int(w * esc), int(h * esc)))
        nome_tipo = {"bau": "BAÚ ABERTO", "tesouro": "TESOURO", "fim": "FIM DE PARTIDA"}[tipo]
        top = tk.Toplevel(self.root)
        top.title(f"Arraste em volta do aviso de {nome_tipo} e aperte Enter (Esc cancela)")
        top.attributes("-topmost", True)
        foto = ImageTk.PhotoImage(mini)
        cv = tk.Canvas(top, width=mini.width, height=mini.height, cursor="cross", highlightthickness=0)
        cv.pack()
        cv.create_image(0, 0, anchor="nw", image=foto)
        cv.foto = foto
        r = {"id": None, "x0": 0, "y0": 0, "x1": 0, "y1": 0}

        def ini(e):
            r.update(x0=e.x, y0=e.y, x1=e.x, y1=e.y)
            if r["id"]:
                cv.delete(r["id"])
            r["id"] = cv.create_rectangle(e.x, e.y, e.x, e.y, outline=OURO, width=2)

        def mov(e):
            r.update(x1=e.x, y1=e.y)
            cv.coords(r["id"], r["x0"], r["y0"], e.x, e.y)

        def salvar(_e=None):
            x0, x1 = sorted((r["x0"], r["x1"]))
            y0, y1 = sorted((r["y0"], r["y1"]))
            X0, Y0, X1, Y1 = (int(v / esc) for v in (x0, y0, x1, y1))
            if X1 - X0 < 10 or Y1 - Y0 < 10:
                messagebox.showwarning("Recorte", "Selecione uma área maior.", parent=top)
                return
            pasta = os.path.join(PASTA_MODELOS, tipo)
            os.makedirs(pasta, exist_ok=True)
            nome = datetime.now().strftime("%Y%m%d_%H%M%S")
            cv2.imwrite(os.path.join(pasta, nome + ".png"), img_bgr[Y0:Y1, X0:X1])
            with open(os.path.join(pasta, nome + ".json"), "w", encoding="utf-8") as f:
                json.dump({"x": X0, "y": Y0, "largura_tela": w, "altura_tela": h, "metodo": "cinza",
                           "limiar": self.cfg["limiar_padrao"], "margem": self.cfg["margem_padrao_px"]}, f, indent=2)
            self.detector.recarregar = True
            top.destroy()

        cv.bind("<ButtonPress-1>", ini)
        cv.bind("<B1-Motion>", mov)
        top.bind("<Return>", salvar)
        top.bind("<Escape>", lambda e: top.destroy())
        top.focus_force()

    # ---- bandeja
    def criar_icone_bandeja(self):
        import pystray
        from PIL import Image, ImageDraw
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((6, 18, 58, 56), 6, fill=(150, 90, 30), outline=(255, 211, 77), width=4)
        d.rectangle((6, 30, 58, 34), fill=(255, 211, 77))
        d.rectangle((27, 28, 37, 40), fill=(255, 211, 77))
        p = lambda ev: (lambda icon, item: self.fila.put(ev))
        self.icone = pystray.Icon("contador_baus", img, "Contador de Baús", pystray.Menu(
            pystray.MenuItem("Abrir", p("mostrar"), default=True),
            pystray.MenuItem("+1 baú", p("bau")),
            pystray.MenuItem("+1 tesouro", p("tesouro")),
            pystray.MenuItem("Finalizar partida", p("finalizar")),
            pystray.MenuItem("Rotas de baús", p("rotas")),
            pystray.MenuItem("Sair", p("sair")),
        ))
        self.icone.run_detached()

    def mostrar(self):
        self.root.deiconify()
        self.root.lift()

    def sair(self):
        if self.icone:
            self.icone.stop()
        self.root.destroy()

    def rodar(self):
        self.root.mainloop()


class JanelaRotas:
    """Mapa com os baús. Clique onde vocês caíram e o programa monta a melhor rota."""
    LADO = 620

    def __init__(self, app):
        import rotas
        from PIL import Image, ImageDraw, ImageTk
        self.rotas, self.ImageTk = rotas, ImageTk
        self.app = app
        if getattr(app, "_janela_rotas", None) and app._janela_rotas.top.winfo_exists():
            app._janela_rotas.top.deiconify()
            app._janela_rotas.top.lift()
            return
        try:
            self.plan = app.planejador
        except Exception as e:
            messagebox.showerror("Rotas", f"Não consegui abrir o mapa:\n{e}")
            return
        app._janela_rotas = self
        self.mapa = self.plan.mapa
        base = Image.open(self.mapa.imagem).convert("RGB")
        self.esc = self.LADO / max(base.size)
        # mapa base com um pontinho em cada baú (sem rota)
        d = ImageDraw.Draw(base)
        for x, y, _ in self.mapa.pontos:
            X, Y = self.mapa.para_pixel(x, y)
            d.ellipse((X - 2, Y - 2, X + 2, Y + 2), fill=(255, 211, 77), outline=(60, 40, 0))
        self.base = base
        self.inicio = None
        self.etapas = []

        top = self.top = tk.Toplevel(app.root)
        top.title("Rotas de baús")
        top.configure(bg=BG)
        esq = tk.Frame(top, bg=BG)
        esq.pack(side="left", padx=8, pady=8)
        self.cv = tk.Canvas(esq, width=int(base.width * self.esc), height=int(base.height * self.esc),
                            highlightthickness=0, cursor="crosshair", bg="black")
        self.cv.pack()
        self.cv.bind("<Button-1>", self.clicou)
        tk.Label(esq, text=f"Clique no mapa onde vocês caíram  •  {len(self.mapa.pontos)} baús  •  "
                           f"dados: fortnite.gg v{self.mapa.versao}",
                 bg=BG, fg="#b9b0d9", font=("Segoe UI", 8)).pack(anchor="w", pady=(4, 0))

        dir_ = tk.Frame(top, bg=BG)
        dir_.pack(side="left", fill="y", padx=(0, 10), pady=8)
        rot = lambda t: tk.Label(dir_, text=t, bg=BG, fg="white", font=("Segoe UI", 9, "bold"))
        rot("Onde vocês caíram:").pack(anchor="w")
        nomes = sorted(l["nome"].title().replace("'S", "'s") for l in self.mapa.locais)
        self._locais = {l["nome"].title().replace("'S", "'s"): l for l in self.mapa.locais}
        self.cb = ttk.Combobox(dir_, values=nomes, state="readonly", width=28)
        self.cb.pack(anchor="w", pady=(2, 8))
        self.cb.bind("<<ComboboxSelected>>", self.escolheu_local)
        rot("Tempo de saque (minutos):").pack(anchor="w")
        self.minutos = tk.IntVar(value=int(app.cfg["rota_minutos"]))
        tk.Spinbox(dir_, from_=2, to=20, textvariable=self.minutos, width=5,
                   command=self.calcular).pack(anchor="w", pady=(2, 8))
        bts = tk.Frame(dir_, bg=BG)
        bts.pack(anchor="w", pady=(0, 6))
        app._botao(bts, "Melhores pousos", self.melhores).pack(side="left", padx=(0, 4))
        self.lbl_res = tk.Label(dir_, text="", bg=BG, fg=OURO, font=("Segoe UI", 11, "bold"), justify="left")
        self.lbl_res.pack(anchor="w")
        self.lista = tk.Listbox(dir_, width=40, height=16, bg=BG2, fg="white", relief="flat",
                                selectbackground=ROXO, font=("Segoe UI", 9), activestyle="none")
        self.lista.pack(anchor="w", fill="y", expand=True, pady=4)
        bt2 = tk.Frame(dir_, bg=BG)
        bt2.pack(anchor="w", pady=(4, 0))
        tk.Button(bt2, text="✔ Usar esta rota no jogo", command=self.usar, bg=OURO, fg="#1b1530", relief="flat",
                  font=("Segoe UI", 9, "bold"), padx=8, pady=3).pack(side="left", padx=(0, 4))
        app._botao(bt2, "Parar rota", self.parar).pack(side="left")
        tk.Label(dir_, text="No jogo: a etapa avança sozinha quando você abre\nos baús dela. F10 pula etapa, Shift+F10 volta.",
                 bg=BG, fg="#b9b0d9", font=("Segoe UI", 8), justify="left").pack(anchor="w", pady=(6, 0))
        if app.rota:
            self.inicio, self.etapas = app.rota.inicio, app.rota.etapas
            self.mostrar_lista()
        self.desenhar()

    def desenhar(self):
        if self.etapas or self.inicio:
            img = self.rotas.desenhar_rota(self.mapa, self.etapas, -1, self.inicio, recorte=False, base=self.base.copy())
        else:
            img = self.base
        img = img.resize((int(img.width * self.esc), int(img.height * self.esc)))
        self._foto = self.ImageTk.PhotoImage(img)
        self.cv.delete("all")
        self.cv.create_image(0, 0, anchor="nw", image=self._foto)

    def clicou(self, e):
        self.inicio = self.mapa.de_pixel(e.x / self.esc, e.y / self.esc)
        self.cb.set("")
        self.calcular()

    def escolheu_local(self, _e=None):
        l = self._locais[self.cb.get()]
        self.inicio = (l["x"], l["y"])
        self.calcular()

    def calcular(self):
        if not self.inicio:
            return
        try:
            m = max(1, int(self.minutos.get()))
        except (tk.TclError, ValueError):
            return
        self.app.cfg["rota_minutos"] = m
        salvar_config(self.app.cfg)
        self.top.config(cursor="watch")
        self.top.update_idletasks()
        paradas, self.tempo = self.plan.rota(*self.inicio, minutos=m)
        self.top.config(cursor="")
        self.etapas = self.rotas.juntar_etapas(paradas)
        self.mostrar_lista()
        self.desenhar()

    def mostrar_lista(self):
        self.lista.delete(0, "end")
        total = sum(e.baus for e in self.etapas)
        onde = self.mapa.nome_perto(*self.inicio) if self.inicio else "?"
        self.lbl_res.config(text=f"{total} baús em ~{self.minutos.get()} min\nsaindo de {onde}")
        for k, e in enumerate(self.etapas, 1):
            self.lista.insert("end", f"{k:>2}. {e.nome}  —  {e.baus} baú{'s' if e.baus > 1 else ''}")

    def melhores(self):
        self.top.config(cursor="watch")
        self.top.update_idletasks()
        res = self.plan.melhores_pousos(float(self.minutos.get()), n=6)
        self.top.config(cursor="")
        self.lista.delete(0, "end")
        self.lbl_res.config(text=f"Melhores pousos ({self.minutos.get()} min):")
        for baus, nome, _t in res:
            self.lista.insert("end", f"{baus:>3} baús  —  {nome.title().replace(chr(39) + 'S', chr(39) + 's')}")
        self.lista.insert("end", "")
        self.lista.insert("end", "Escolha um deles em 'Onde vocês caíram'.")

    def usar(self):
        if not self.etapas:
            messagebox.showinfo("Rotas", "Primeiro clique no mapa (ou escolha o lugar) pra montar a rota.", parent=self.top)
            return
        self.app.usar_rota(self.rotas.RotaAtiva(self.etapas, self.inicio, self.minutos.get()))
        self.top.withdraw()

    def parar(self):
        self.app.usar_rota(None)


if __name__ == "__main__":
    # impede abrir duas vezes (contaria tudo em dobro)
    _mutex = ctypes.windll.kernel32.CreateMutexW(None, False, "ContadorDeBausFortnite")
    if ctypes.windll.kernel32.GetLastError() == 183:
        ctypes.windll.user32.MessageBoxW(None, "O Contador de Baús já está aberto.\nProcure o ícone de baú perto do relógio.",
                                         "Contador de Baús", 0x40)
        sys.exit(0)
    App().rodar()
