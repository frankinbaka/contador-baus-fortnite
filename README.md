# Contador de Baús e Tesouros — Fortnite

Programinha para Windows que roda em segundo plano e **conta sozinho os baús e tesouros** que você abre em cada partida de Fortnite, salva o histórico e mostra o **total**.

## ⬇️ Download

Baixe o **`ContadorDeBaus.exe`** na página de [Releases](../../releases/latest). Não precisa instalar nada: é só abrir.

> Se aparecer **"O Windows protegeu o computador"**, clique em **Mais informações → Executar assim mesmo**. O aviso aparece porque o programa não tem assinatura digital.

## O que ele faz

- **Conta cada baú** pelo aviso **"+EXP / BAÚ"** (com o BAÚ branco ou amarelo, qualquer valor de EXP).
- **Conta cada tesouro** pelo selo **"VOCÊ ENCONTROU …"**.
- **Fecha a partida sozinho** na tela **"SUA COLOCAÇÃO"** ou **"RESUMO DA PARTIDA"**, e conta os tesouros mostrados no resumo.
- **Histórico**: 1ª partida 20 baús, 2ª 30 baús… com o total e a média.
- **Contador na tela**: uma caixinha com BAÚS e TESOUROS por cima do jogo, no canto que você escolher.
- **Rotas de baús**: clique no mapa onde caiu e ele monta a rota que abre mais baús no tempo escolhido, mostrando a etapa atual e um mapinha no contador do jogo.
- **Pasta `conferir`**: guarda uma foto pequena de cada contagem (as últimas 200), pra você conferir se algo foi contado errado.

O programa **só lê a imagem da tela** (como OBS ou Medal). Não mexe no jogo nem na memória dele.

## Atalhos (funcionam com o jogo aberto)

| Tecla | Ação |
|---|---|
| F8 / F7 | +1 / −1 baú |
| F6 / Ctrl+F6 | +1 / −1 tesouro |
| F9 | finalizar a partida na mão |
| F10 / Shift+F10 | próxima / anterior etapa da rota |
| Ctrl+Shift+B / T / F | ensinar um modelo novo de baú / tesouro / fim de partida |
| Del (na lista) | apagar uma partida |

## Requisitos e limitações

- Windows 10/11, Fortnite em **português**, tela **16:9** (1080p, 1440p…).
- O contador na tela só aparece por cima do jogo no modo **"Tela cheia em janela"**.
- Em outro idioma ou com outro HUD, ensine os avisos com **Ctrl+Shift+B/T/F**: no jogo, com o aviso na tela, aperte o atalho, volte ao programa, arraste em volta do aviso e aperte Enter.

## Rodar pelo código

```bash
py -m pip install -r requirements.txt
py contador_baus.py
```

Para gerar o `.exe`: rode `build.bat` (o arquivo sai em `dist\ContadorDeBaus.exe`).

## Como funciona

A cada 0,15 s o programa tira um print da tela (com `mss`) e procura, numa área pequena, as imagens da pasta `modelos/` (com `opencv`):

- **Baú**: o texto "BAÚ" (máscara de cor branca ou amarela) **e** o "EXP" logo acima, na altura certa, em **duas olhadas seguidas**. Isso evita contar marcadores de distância ("846 m") que passam pelo mesmo lugar.
- **Tesouro / fim**: comparação em tons de cinza.
- **Tesouros do resumo**: conta os quadros dourados em "TESOURO ENCONTRADO".

**Rotas**: os baús vêm do mapa do [fortnite.gg](https://fortnite.gg) (pasta `mapa/`). Baús próximos viram uma parada, e o programa escolhe as paradas que dão mais baús dentro do tempo (inserção gulosa + 2-opt), considerando ~6 m/s andando e ~7 s por baú.

Os dados ficam em `dados_baus.json` e as configurações em `config.json`, na mesma pasta do programa.
