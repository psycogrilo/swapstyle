#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SwapStyle Web — Flask Backend
Arquivo principal: app.py
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3, hashlib, uuid, os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "swapstyle-dev-secret-2024")
DB_FILE = os.environ.get("DB_FILE", "swapstyle.db")

CATEGORIAS = ["Vestido","Blusa","Calça","Saia","Shorts","Blazer",
              "Casaco","Jaqueta","Acessório","Bolsa","Sapato","Sandália",
              "Tênis","Bijuteria","Outros"]
TAMANHOS   = ["PP","P","M","G","GG","XGG","34","36","38","40","42","44","46","48","Único"]
CONDICOES  = ["Novo com etiqueta","Novo sem etiqueta","Excelente","Bom estado","Usado"]
PLANS      = {
    "free":    {"nome":"Free",    "preco":0.0,  "trocas":3},
    "style":   {"nome":"Style",   "preco":19.90,"trocas":999},
    "premium": {"nome":"Premium", "preco":39.90,"trocas":999},
}
SWAP_COMMISSION = 0.08

# ── DB ──────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL, telefone TEXT, cpf_hash TEXT,
        senha_hash TEXT NOT NULL, nome TEXT, cidade TEXT, estado TEXT,
        plano TEXT DEFAULT 'free', swapcoin REAL DEFAULT 0.0,
        nota_media REAL DEFAULT 5.0, total_trocas INTEGER DEFAULT 0,
        trocas_mes INTEGER DEFAULT 0, mes_reset TEXT,
        verificada INTEGER DEFAULT 0, ativa INTEGER DEFAULT 1,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP, bio TEXT DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS pecas (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, titulo TEXT NOT NULL,
        categoria TEXT NOT NULL, tamanho TEXT NOT NULL, condicao TEXT NOT NULL,
        descricao TEXT, valor_est REAL NOT NULL, disponivel INTEGER DEFAULT 1,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES usuarios(id)
    );
    CREATE TABLE IF NOT EXISTS matches (
        id TEXT PRIMARY KEY, peca_a TEXT NOT NULL, peca_b TEXT NOT NULL,
        user_a TEXT NOT NULL, user_b TEXT NOT NULL,
        status TEXT DEFAULT 'pendente', swapcoin_diff REAL DEFAULT 0.0,
        rastreio_a TEXT, rastreio_b TEXT,
        confirmado_a INTEGER DEFAULT 0, confirmado_b INTEGER DEFAULT 0,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP, concluido_em TEXT,
        FOREIGN KEY (peca_a) REFERENCES pecas(id),
        FOREIGN KEY (peca_b) REFERENCES pecas(id)
    );
    CREATE TABLE IF NOT EXISTS curtidas (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, peca_id TEXT NOT NULL,
        tipo TEXT NOT NULL, criado_em TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, peca_id)
    );
    CREATE TABLE IF NOT EXISTS avaliacoes (
        id TEXT PRIMARY KEY, match_id TEXT NOT NULL,
        avaliador_id TEXT NOT NULL, avaliado_id TEXT NOT NULL,
        nota INTEGER NOT NULL, comentario TEXT,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS mensagens (
        id TEXT PRIMARY KEY, match_id TEXT NOT NULL,
        user_id TEXT NOT NULL, texto TEXT NOT NULL,
        criado_em TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)
    conn.commit(); conn.close()

def hash_val(v): return hashlib.sha256(v.encode()).hexdigest()
def novo_id(): return str(uuid.uuid4())

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Não autenticada"}), 401
        return f(*args, **kwargs)
    return decorated

def get_current_user():
    if "user_id" not in session: return None
    conn = get_db()
    u = conn.execute("SELECT * FROM usuarios WHERE id=?", (session["user_id"],)).fetchone()
    conn.close()
    return u

# ── PAGES ───────────────────────────────────────────────────────
@app.route("/")
def index():
    if "user_id" in session: return redirect(url_for("app_page"))
    return render_template("landing.html")

@app.route("/app")
def app_page():
    if "user_id" not in session: return redirect(url_for("index"))
    user = get_current_user()
    return render_template("app.html", user=dict(user), categorias=CATEGORIAS,
                           tamanhos=TAMANHOS, condicoes=CONDICOES, plans=PLANS)

# ── AUTH API ────────────────────────────────────────────────────
@app.route("/api/login", methods=["POST"])
def api_login():
    d = request.json
    conn = get_db()
    u = conn.execute("SELECT * FROM usuarios WHERE email=? AND senha_hash=? AND ativa=1",
                     (d["email"].lower(), hash_val(d["senha"]))).fetchone()
    conn.close()
    if not u: return jsonify({"error": "E-mail ou senha incorretos"}), 401
    session["user_id"] = u["id"]
    return jsonify({"ok": True, "username": u["username"], "nome": u["nome"]})

@app.route("/api/cadastro", methods=["POST"])
def api_cadastro():
    d = request.json
    if not d.get("email") or not d.get("username") or not d.get("senha"):
        return jsonify({"error": "Campos obrigatórios faltando"}), 400
    if len(d["senha"]) < 6:
        return jsonify({"error": "Senha deve ter ao menos 6 caracteres"}), 400
    conn = get_db()
    existe = conn.execute("SELECT id FROM usuarios WHERE email=? OR username=?",
                          (d["email"].lower(), d["username"].lower())).fetchone()
    if existe:
        conn.close()
        return jsonify({"error": "E-mail ou @username já cadastrado"}), 409
    uid = novo_id()
    mes = datetime.now().strftime("%Y-%m")
    conn.execute("""INSERT INTO usuarios (id,username,email,telefone,cpf_hash,senha_hash,nome,cidade,estado,mes_reset)
                    VALUES (?,?,?,?,?,?,?,?,?,?)""",
                 (uid, d["username"].lower(), d["email"].lower(), d.get("telefone",""),
                  hash_val(d["cpf"]) if d.get("cpf") else None,
                  hash_val(d["senha"]), d.get("nome",""), d.get("cidade",""), d.get("estado","").upper(), mes))
    conn.commit(); conn.close()
    session["user_id"] = uid
    return jsonify({"ok": True})

@app.route("/api/logout", methods=["POST"])
def api_logout():
    session.clear()
    return jsonify({"ok": True})

# ── USER API ────────────────────────────────────────────────────
@app.route("/api/me")
@login_required
def api_me():
    u = get_current_user()
    conn = get_db()
    pending = conn.execute("SELECT COUNT(*) as n FROM matches WHERE (user_a=? OR user_b=?) AND status='pendente'",
                           (u["id"],u["id"])).fetchone()["n"]
    andamento = conn.execute("SELECT COUNT(*) as n FROM matches WHERE (user_a=? OR user_b=?) AND status='andamento'",
                             (u["id"],u["id"])).fetchone()["n"]
    conn.close()
    return jsonify({**dict(u), "notif_matches": pending, "notif_andamento": andamento})

@app.route("/api/me/bio", methods=["PUT"])
@login_required
def api_update_bio():
    d = request.json
    conn = get_db()
    conn.execute("UPDATE usuarios SET bio=? WHERE id=?", (d.get("bio","")[:200], session["user_id"]))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/me/verificar", methods=["POST"])
@login_required
def api_verificar():
    conn = get_db()
    conn.execute("UPDATE usuarios SET verificada=1 WHERE id=?", (session["user_id"],))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/me/plano", methods=["PUT"])
@login_required
def api_plano():
    d = request.json
    plano = d.get("plano")
    if plano not in PLANS: return jsonify({"error": "Plano inválido"}), 400
    conn = get_db()
    conn.execute("UPDATE usuarios SET plano=? WHERE id=?", (plano, session["user_id"]))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/me/swapcoin", methods=["POST"])
@login_required
def api_comprar_coins():
    d = request.json
    qtd = float(d.get("qtd", 0))
    if qtd <= 0: return jsonify({"error": "Quantidade inválida"}), 400
    conn = get_db()
    conn.execute("UPDATE usuarios SET swapcoin=swapcoin+? WHERE id=?", (qtd, session["user_id"]))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

# ── PEÇAS API ───────────────────────────────────────────────────
@app.route("/api/pecas", methods=["GET"])
@login_required
def api_explorar():
    cat = request.args.get("categoria")
    tam = request.args.get("tamanho")
    conn = get_db()
    q = """SELECT p.*, u.username, u.nota_media, u.cidade, u.estado, u.total_trocas, u.verificada
           FROM pecas p JOIN usuarios u ON p.user_id=u.id
           WHERE p.user_id!=? AND p.disponivel=1
             AND p.id NOT IN (SELECT peca_id FROM curtidas WHERE user_id=?)"""
    params = [session["user_id"], session["user_id"]]
    if cat: q += " AND p.categoria=?"; params.append(cat)
    if tam: q += " AND p.tamanho=?";   params.append(tam)
    q += " ORDER BY u.nota_media DESC, p.criado_em DESC LIMIT 30"
    pecas = [dict(p) for p in conn.execute(q, params).fetchall()]
    conn.close()
    return jsonify(pecas)

@app.route("/api/pecas/minhas")
@login_required
def api_minhas_pecas():
    conn = get_db()
    pecas = [dict(p) for p in conn.execute(
        "SELECT * FROM pecas WHERE user_id=? ORDER BY criado_em DESC", (session["user_id"],)
    ).fetchall()]
    conn.close()
    return jsonify(pecas)

@app.route("/api/pecas", methods=["POST"])
@login_required
def api_criar_peca():
    d = request.json
    if not d.get("titulo") or not d.get("categoria") or not d.get("tamanho"):
        return jsonify({"error": "Campos obrigatórios faltando"}), 400
    conn = get_db()
    pid = novo_id()
    conn.execute("""INSERT INTO pecas (id,user_id,titulo,categoria,tamanho,condicao,descricao,valor_est)
                    VALUES (?,?,?,?,?,?,?,?)""",
                 (pid, session["user_id"], d["titulo"], d["categoria"], d["tamanho"],
                  d.get("condicao","Bom estado"), d.get("descricao",""), float(d.get("valor_est",0))))
    conn.commit(); conn.close()
    return jsonify({"ok": True, "id": pid})

@app.route("/api/pecas/<pid>", methods=["DELETE"])
@login_required
def api_deletar_peca(pid):
    conn = get_db()
    conn.execute("DELETE FROM pecas WHERE id=? AND user_id=?", (pid, session["user_id"]))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/pecas/<pid>/toggle", methods=["PUT"])
@login_required
def api_toggle_peca(pid):
    conn = get_db()
    p = conn.execute("SELECT disponivel FROM pecas WHERE id=? AND user_id=?", (pid, session["user_id"])).fetchone()
    if not p: conn.close(); return jsonify({"error": "Não encontrada"}), 404
    novo = 0 if p["disponivel"] else 1
    conn.execute("UPDATE pecas SET disponivel=? WHERE id=?", (novo, pid))
    conn.commit(); conn.close()
    return jsonify({"ok": True, "disponivel": novo})

# ── CURTIDAS & MATCH ────────────────────────────────────────────
@app.route("/api/curtir", methods=["POST"])
@login_required
def api_curtir():
    d = request.json
    peca_id = d["peca_id"]
    tipo    = d["tipo"]  # curtir | passar
    conn = get_db()
    try:
        conn.execute("INSERT INTO curtidas (id,user_id,peca_id,tipo) VALUES (?,?,?,?)",
                     (novo_id(), session["user_id"], peca_id, tipo))
        conn.commit()
    except: conn.close(); return jsonify({"match": False})

    if tipo != "curtir":
        conn.close()
        return jsonify({"match": False})

    # Verifica match mútuo
    dona = conn.execute("SELECT user_id FROM pecas WHERE id=?", (peca_id,)).fetchone()
    if not dona: conn.close(); return jsonify({"match": False})

    candidato = conn.execute("""
        SELECT c.peca_id as minha_peca FROM curtidas c
        JOIN pecas p ON c.peca_id=p.id
        WHERE c.user_id=? AND p.user_id=? AND c.tipo='curtir'
          AND c.peca_id NOT IN (SELECT peca_a FROM matches UNION SELECT peca_b FROM matches)
        LIMIT 1
    """, (dona["user_id"], session["user_id"])).fetchone()

    if not candidato:
        conn.close()
        return jsonify({"match": False})

    minha_peca_id = candidato["minha_peca"]
    val_a = conn.execute("SELECT valor_est,titulo FROM pecas WHERE id=?", (minha_peca_id,)).fetchone()
    val_b = conn.execute("SELECT valor_est,titulo FROM pecas WHERE id=?", (peca_id,)).fetchone()
    diff  = (val_b["valor_est"] - val_a["valor_est"]) if val_a and val_b else 0.0

    mid = novo_id()
    conn.execute("INSERT INTO matches (id,peca_a,peca_b,user_a,user_b,swapcoin_diff) VALUES (?,?,?,?,?,?)",
                 (mid, minha_peca_id, peca_id, session["user_id"], dona["user_id"], diff))
    conn.commit(); conn.close()

    return jsonify({"match": True, "match_id": mid,
                    "titulo_a": val_a["titulo"] if val_a else "",
                    "titulo_b": val_b["titulo"] if val_b else "",
                    "diff": diff})

# ── MATCHES API ─────────────────────────────────────────────────
@app.route("/api/matches")
@login_required
def api_matches():
    conn = get_db()
    matches = conn.execute("""
        SELECT m.*, pa.titulo as titulo_a, pa.valor_est as val_a,
               pb.titulo as titulo_b, pb.valor_est as val_b,
               ua.username as nome_a, ub.username as nome_b,
               ua.nota_media as nota_a, ub.nota_media as nota_b,
               ua.verificada as veri_a, ub.verificada as veri_b
        FROM matches m
        JOIN pecas pa ON m.peca_a=pa.id JOIN pecas pb ON m.peca_b=pb.id
        JOIN usuarios ua ON m.user_a=ua.id JOIN usuarios ub ON m.user_b=ub.id
        WHERE m.user_a=? OR m.user_b=?
        ORDER BY m.criado_em DESC
    """, (session["user_id"], session["user_id"])).fetchall()
    conn.close()
    return jsonify([dict(m) for m in matches])

@app.route("/api/matches/<mid>/aceitar", methods=["POST"])
@login_required
def api_aceitar(mid):
    conn = get_db()
    m = conn.execute("SELECT * FROM matches WHERE id=?", (mid,)).fetchone()
    if not m: conn.close(); return jsonify({"error": "Não encontrado"}), 404
    conn.execute("UPDATE matches SET status='andamento' WHERE id=?", (mid,))
    conn.execute("UPDATE pecas SET disponivel=0 WHERE id=? OR id=?", (m["peca_a"], m["peca_b"]))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/matches/<mid>/recusar", methods=["POST"])
@login_required
def api_recusar(mid):
    conn = get_db()
    conn.execute("UPDATE matches SET status='cancelado' WHERE id=?", (mid,))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/matches/<mid>/rastreio", methods=["POST"])
@login_required
def api_rastreio(mid):
    d = request.json
    conn = get_db()
    m = conn.execute("SELECT * FROM matches WHERE id=?", (mid,)).fetchone()
    if not m: conn.close(); return jsonify({"error":"Não encontrado"}), 404
    campo = "rastreio_a" if m["user_a"] == session["user_id"] else "rastreio_b"
    conn.execute(f"UPDATE matches SET {campo}=? WHERE id=?", (d["codigo"], mid))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/matches/<mid>/confirmar", methods=["POST"])
@login_required
def api_confirmar(mid):
    conn = get_db()
    m = conn.execute("SELECT * FROM matches WHERE id=?", (mid,)).fetchone()
    if not m: conn.close(); return jsonify({"error":"Não encontrado"}), 404
    campo = "confirmado_a" if m["user_a"] == session["user_id"] else "confirmado_b"
    conn.execute(f"UPDATE matches SET {campo}=1 WHERE id=?", (mid,))
    conn.commit()
    m2 = conn.execute("SELECT * FROM matches WHERE id=?", (mid,)).fetchone()
    concluido = False
    if m2["confirmado_a"] and m2["confirmado_b"]:
        conn.execute("UPDATE matches SET status='concluido', concluido_em=CURRENT_TIMESTAMP WHERE id=?", (mid,))
        for uid in [m["user_a"], m["user_b"]]:
            conn.execute("UPDATE usuarios SET total_trocas=total_trocas+1, trocas_mes=trocas_mes+1 WHERE id=?", (uid,))
        conn.commit()
        concluido = True
    conn.close()
    return jsonify({"ok": True, "concluido": concluido})

# ── MENSAGENS ───────────────────────────────────────────────────
@app.route("/api/matches/<mid>/mensagens")
@login_required
def api_get_msgs(mid):
    conn = get_db()
    msgs = conn.execute("""SELECT m.texto, m.criado_em, u.username, u.id as uid
                           FROM mensagens m JOIN usuarios u ON m.user_id=u.id
                           WHERE m.match_id=? ORDER BY m.criado_em""", (mid,)).fetchall()
    conn.close()
    return jsonify([dict(msg) for msg in msgs])

@app.route("/api/matches/<mid>/mensagens", methods=["POST"])
@login_required
def api_send_msg(mid):
    d = request.json
    if not d.get("texto","").strip(): return jsonify({"error":"Vazio"}), 400
    conn = get_db()
    conn.execute("INSERT INTO mensagens (id,match_id,user_id,texto) VALUES (?,?,?,?)",
                 (novo_id(), mid, session["user_id"], d["texto"].strip()))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

# ── AVALIAÇÕES ──────────────────────────────────────────────────
@app.route("/api/avaliacoes/pendentes")
@login_required
def api_pendentes():
    conn = get_db()
    pendentes = conn.execute("""
        SELECT m.id, m.user_a, m.user_b, pa.titulo as titulo_a, pb.titulo as titulo_b,
               ua.username as nome_a, ub.username as nome_b
        FROM matches m
        JOIN pecas pa ON m.peca_a=pa.id JOIN pecas pb ON m.peca_b=pb.id
        JOIN usuarios ua ON m.user_a=ua.id JOIN usuarios ub ON m.user_b=ub.id
        WHERE (m.user_a=? OR m.user_b=?) AND m.status='concluido'
          AND m.id NOT IN (SELECT match_id FROM avaliacoes WHERE avaliador_id=?)
    """, (session["user_id"], session["user_id"], session["user_id"])).fetchall()
    conn.close()
    return jsonify([dict(p) for p in pendentes])

@app.route("/api/avaliacoes", methods=["POST"])
@login_required
def api_avaliar():
    d = request.json
    conn = get_db()
    m = conn.execute("SELECT * FROM matches WHERE id=?", (d["match_id"],)).fetchone()
    if not m: conn.close(); return jsonify({"error":"Match não encontrado"}), 404
    avaliado = m["user_b"] if m["user_a"] == session["user_id"] else m["user_a"]
    conn.execute("INSERT INTO avaliacoes (id,match_id,avaliador_id,avaliado_id,nota,comentario) VALUES (?,?,?,?,?,?)",
                 (novo_id(), d["match_id"], session["user_id"], avaliado, int(d["nota"]), d.get("comentario","")))
    media = conn.execute("SELECT AVG(nota) as m FROM avaliacoes WHERE avaliado_id=?", (avaliado,)).fetchone()
    if media and media["m"]:
        conn.execute("UPDATE usuarios SET nota_media=? WHERE id=?", (round(media["m"],2), avaliado))
    conn.commit(); conn.close()
    return jsonify({"ok": True})

@app.route("/api/avaliacoes/<uid>")
@login_required
def api_get_avaliacoes(uid):
    conn = get_db()
    avs = conn.execute("""SELECT a.nota, a.comentario, a.criado_em, u.username
                          FROM avaliacoes a JOIN usuarios u ON a.avaliador_id=u.id
                          WHERE a.avaliado_id=? ORDER BY a.criado_em DESC LIMIT 10""", (uid,)).fetchall()
    conn.close()
    return jsonify([dict(a) for a in avs])

# ── BUSCA ────────────────────────────────────────────────────────
@app.route("/api/buscar")
@login_required
def api_buscar():
    q = request.args.get("q","").strip()
    tipo = request.args.get("tipo","peca")
    conn = get_db()
    if tipo == "peca":
        r = conn.execute("""SELECT p.*, u.username, u.nota_media, u.cidade, u.verificada
                            FROM pecas p JOIN usuarios u ON p.user_id=u.id
                            WHERE (p.titulo LIKE ? OR p.descricao LIKE ? OR p.categoria LIKE ?)
                              AND p.disponivel=1 AND p.user_id!=?
                            ORDER BY u.nota_media DESC LIMIT 20""",
                         (f"%{q}%",f"%{q}%",f"%{q}%", session["user_id"])).fetchall()
    else:
        r = conn.execute("""SELECT id,username,nome,cidade,estado,nota_media,total_trocas,verificada,bio,plano
                            FROM usuarios WHERE username LIKE ? AND ativa=1 AND id!=?
                            ORDER BY nota_media DESC LIMIT 10""",
                         (f"%{q}%", session["user_id"])).fetchall()
    conn.close()
    return jsonify([dict(x) for x in r])

# ── MAIN ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"
    print(f"\n  🌸 SwapStyle Web rodando em http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)
