from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, g
import sqlite3
from datetime import datetime, timezone, timedelta
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = 'alerta_nampula_2025_ultra_secret_key'
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alerta.db')

# Mozambique time: CAT = UTC+2
CAT = timezone(timedelta(hours=2))

def now_cat():
    return datetime.now(CAT).strftime('%Y-%m-%d %H:%M:%S')

def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(DB)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db: db.close()

def query(sql, args=(), one=False, commit=False):
    db = get_db()
    cur = db.execute(sql, args)
    if commit:
        db.commit()
        return cur.lastrowid
    return cur.fetchone() if one else cur.fetchall()

def get_site_config():
    try:
        rows = query("SELECT chave, valor FROM configuracao")
        cfg = {r['chave']: r['valor'] for r in rows}
        return {
            'nome':      cfg.get('site_nome',      'Alerta Nampula'),
            'subtitulo': cfg.get('site_subtitulo', 'Sistema de Protecção Comunitária'),
            'email':     cfg.get('site_email',     'heliopaiva111@gmail.com'),
            'telefone':  cfg.get('site_telefone',  '+258 87 441 3363'),
            'endereco':  cfg.get('site_endereco',  'Carrupeia, Nampula'),
            'whatsapp':  cfg.get('site_whatsapp',  ''),
            'facebook':  cfg.get('site_facebook',  ''),
            'twitter':   cfg.get('site_twitter',   ''),
        }
    except:
        return {
            'nome': 'Alerta Nampula', 'subtitulo': 'Sistema de Protecção Comunitária',
            'email': 'heliopaiva111@gmail.com', 'telefone': '+258 87 441 3363',
            'endereco': 'Carrupeia, Nampula', 'whatsapp': '', 'facebook': '', 'twitter': '',
        }

def init_db():
    with app.app_context():
        db = get_db()
        db.executescript("""
        CREATE TABLE IF NOT EXISTS admin(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          nome TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
          password TEXT NOT NULL, nivel TEXT DEFAULT 'admin');
        CREATE TABLE IF NOT EXISTS alerta(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          titulo TEXT NOT NULL, tipo TEXT NOT NULL, conteudo TEXT NOT NULL,
          data TEXT DEFAULT (datetime('now')), ativo INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS familia(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          bairro TEXT NOT NULL, numero INTEGER NOT NULL, situacao TEXT NOT NULL,
          abrigo TEXT NOT NULL, necessidades TEXT NOT NULL,
          data TEXT DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS zona(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          nome TEXT NOT NULL, capacidade INTEGER NOT NULL, recursos TEXT NOT NULL,
          ativa INTEGER DEFAULT 1);
        CREATE TABLE IF NOT EXISTS apoio(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          tipo TEXT, quantidade TEXT, local_entrega TEXT, contacto TEXT,
          status TEXT DEFAULT 'pendente',
          data TEXT DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS subscricao(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          nome TEXT, telefone TEXT, email TEXT, metodos TEXT, tipo_alertas TEXT,
          data TEXT DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS configuracao(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          chave TEXT UNIQUE NOT NULL, valor TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS ussd_pedido(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          telefone TEXT NOT NULL,
          tipo TEXT NOT NULL,
          descricao TEXT NOT NULL,
          status TEXT DEFAULT 'pendente',
          data TEXT DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS ussd_voluntario(
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          nome TEXT NOT NULL,
          telefone TEXT NOT NULL UNIQUE,
          habilidades TEXT,
          data TEXT DEFAULT (datetime('now')));
        """)
        try:
            db.execute("ALTER TABLE apoio ADD COLUMN status TEXT DEFAULT 'pendente'")
        except: pass
        db.commit()

        if not db.execute("SELECT 1 FROM admin LIMIT 1").fetchone():
            db.executemany("INSERT INTO admin(nome,email,password,nivel) VALUES(?,?,?,?)",[
                ('Helio Paiva','heliopaiva111@gmail.com','Abacarito','master'),
                ('Ana Macuacua','ana@alerta.co.mz','Admin2025!','admin'),
            ])
        if not db.execute("SELECT 1 FROM alerta LIMIT 1").fetchone():
            db.executemany("INSERT INTO alerta(titulo,tipo,conteudo,data) VALUES(?,?,?,?)",[
                ('Alerta Meteorológico Nampula','urgente','Previsão de chuvas fortes nos próximos 3 dias. Evite zonas baixas e margens de rios.', now_cat()),
                ('Segurança Pública','atencao','Atenção redobrada em locais públicos e mercados.', now_cat()),
                ('Saúde Pública','informativo','Campanha de vacinação contra a cólera em todos os centros de saúde até final do mês.', now_cat()),
            ])
        if not db.execute("SELECT 1 FROM familia LIMIT 1").fetchone():
            db.executemany("INSERT INTO familia(bairro,numero,situacao,abrigo,necessidades,data) VALUES(?,?,?,?,?,?)",[
                ('Bairro Muahivire',15,'Inundações','Escola Primária','Água, alimentos, cobertores', now_cat()),
                ('Bairro Napipine',27,'Ciclone','Centro Comunitário','Kits de higiene, medicamentos', now_cat()),
            ])
        if not db.execute("SELECT 1 FROM zona LIMIT 1").fetchone():
            db.executemany("INSERT INTO zona(nome,capacidade,recursos) VALUES(?,?,?)",[
                ('Escola Primária de Napipine',200,'Água potável, alimentação garantida'),
                ('Centro Comunitário Municipal',150,'Assistência médica básica, espaço para dormir'),
            ])
        configs = [
            ('site_nome','Alerta Nampula'),('site_subtitulo','Sistema de Protecção Comunitária'),
            ('site_email','heliopaiva111@gmail.com'),('site_telefone','+258 87 441 3363'),
            ('site_endereco','Carrupeia, Nampula'),('site_whatsapp',''),
            ('site_facebook',''),('site_twitter',''),
        ]
        for chave, valor in configs:
            try: db.execute("INSERT OR IGNORE INTO configuracao(chave,valor) VALUES(?,?)", (chave, valor))
            except: pass
        db.commit()

def login_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if not session.get('admin_id'):
            return redirect(url_for('login'))
        return f(*a, **kw)
    return dec

def master_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if not session.get('admin_id'):
            return redirect(url_for('login'))
        if session.get('admin_nivel') != 'master':
            flash('Acesso negado.', 'error')
            return redirect(url_for('admin_dashboard'))
        return f(*a, **kw)
    return dec

def fmt_date(d):
    try: return datetime.strptime(d[:19], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y')
    except: return str(d) if d else ''

def fmt_datetime(d):
    try: return datetime.strptime(d[:19], '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
    except: return str(d) if d else ''


# ═══════════════════════════════════════════════════════════════
#  USSD HANDLER — Africa's Talking
#  Callback URL: https://alerta-nampula.onrender.com/ussd
#  Os dados são os MESMOS do site (mesma BD)
# ═══════════════════════════════════════════════════════════════

@app.route('/ussd', methods=['POST'])
def ussd():
    session_id   = request.form.get('sessionId', '')
    phone_number = request.form.get('phoneNumber', '')
    text         = request.form.get('text', '')

    if not session_id or not phone_number:
        return 'END Erro de sessão. Tente novamente.', 200, {'Content-Type': 'text/plain'}

    partes = text.split('*') if text else []
    resposta = _processar_ussd(partes, phone_number)
    return resposta, 200, {'Content-Type': 'text/plain'}


def _processar_ussd(partes, telefone):
    if not partes or partes[0] == '':
        return _menu_principal()

    opcao = partes[0]
    if opcao == '1': return _menu_alertas(partes)
    if opcao == '2': return _menu_zonas(partes)
    if opcao == '3': return _menu_ajuda(partes, telefone)
    if opcao == '4': return _menu_informacoes(partes)
    if opcao == '5': return _menu_voluntariado(partes, telefone)
    if opcao == '0': return _menu_medico(partes, telefone)
    return 'END Opção inválida. Marque novamente.'


def _menu_principal():
    return (
        'CON ★ ALERTA NAMPULA ★\n'
        '─────────────────────\n'
        '1. Ver Alertas Activos\n'
        '2. Zonas Seguras\n'
        '3. Pedir Ajuda\n'
        '4. Informações\n'
        '5. Voluntariado\n'
        '0. Suporte Médico'
    )


def _menu_alertas(partes):
    # Lê directamente da tabela `alerta` — os mesmos do site
    alertas = query(
        "SELECT * FROM alerta WHERE ativo=1 "
        "ORDER BY CASE tipo WHEN 'urgente' THEN 1 WHEN 'atencao' THEN 2 ELSE 3 END, data DESC "
        "LIMIT 3"
    )

    if len(partes) == 1:
        if not alertas:
            return 'END Sem alertas activos.\nFique seguro!'
        resp = 'CON ALERTAS ACTIVOS:\n'
        for i, a in enumerate(alertas, 1):
            icone = '🔴' if a['tipo'] == 'urgente' else ('🟠' if a['tipo'] == 'atencao' else '🔵')
            resp += f'{i}. {icone} {a["titulo"]}\n'
        resp += '\nDigite o número para detalhes\n0. Voltar'
        return resp

    if partes[1] == '0':
        return _menu_principal()

    try:
        idx = int(partes[1]) - 1
        a = list(alertas)[idx]
        nivel = '🔴 URGENTE' if a['tipo'] == 'urgente' else ('🟠 ATENÇÃO' if a['tipo'] == 'atencao' else '🔵 INFO')
        msg = a['conteudo'][:120]
        sufixo = '...' if len(a['conteudo']) > 120 else ''
        return f'END {nivel}\n{a["titulo"]}\n────────────────\n{msg}{sufixo}'
    except (IndexError, ValueError):
        return 'END Alerta não encontrado.'


def _menu_zonas(partes):
    if len(partes) == 1:
        return (
            'CON ZONAS SEGURAS\n'
            '1. Listar zonas\n'
            '2. Ver recursos\n'
            '0. Voltar'
        )

    if partes[1] == '0':
        return _menu_principal()

    # Lê directamente da tabela `zona` — as mesmas do site
    zonas = query("SELECT * FROM zona WHERE ativa=1 ORDER BY nome")

    if partes[1] == '1':
        if not zonas:
            return 'END Sem zonas seguras registadas.'
        resp = 'END ZONAS SEGURAS:\n────────────────\n'
        for z in zonas:
            resp += f'• {z["nome"]}\n  Cap: {z["capacidade"]} pessoas\n'
        return resp

    if partes[1] == '2':
        if not zonas:
            return 'END Sem dados disponíveis.'
        resp = 'END RECURSOS NAS ZONAS:\n'
        for z in zonas:
            resp += f'• {z["nome"]}:\n  {z["recursos"]}\n'
        return resp

    return 'END Opção inválida.'


def _menu_ajuda(partes, telefone):
    if len(partes) == 1:
        return (
            'CON ⚠ PEDIR AJUDA\n'
            '1. RESGATE URGENTE\n'
            '2. Água potável\n'
            '3. Alimentos\n'
            '4. Medicamentos\n'
            '0. Voltar'
        )

    if partes[1] == '0':
        return _menu_principal()

    tipos = {'1': 'resgate', '2': 'agua', '3': 'comida', '4': 'medicamentos'}
    tipo = tipos.get(partes[1])
    if not tipo:
        return 'END Opção inválida.'

    # Pedir detalhe adicional
    if tipo in ('agua', 'comida') and len(partes) == 2:
        return 'CON Quantas pessoas precisam?'
    if tipo == 'medicamentos' and len(partes) == 2:
        return 'CON Qual medicamento ou emergência?'

    # Construir descrição
    if tipo == 'resgate':
        descricao = 'Resgate urgente via USSD'
    elif tipo == 'agua':
        descricao = f'Água para {partes[2] if len(partes) > 2 else "?"} pessoas'
    elif tipo == 'comida':
        descricao = f'Alimentos para {partes[2] if len(partes) > 2 else "?"} pessoas'
    else:
        descricao = f'Medicamentos: {partes[2] if len(partes) > 2 else "não especificado"}'

    try:
        pid = query(
            "INSERT INTO ussd_pedido(telefone, tipo, descricao, data) VALUES(?,?,?,?)",
            (telefone, tipo, descricao, now_cat()), commit=True
        )
        msgs = {
            'resgate':      f'END ✔ RESGATE SOLICITADO! (Ref#{pid})\nAjuda a caminho.\nLigue 118 se possível.',
            'agua':         f'END ✔ Pedido registado (Ref#{pid})\n{descricao}.',
            'comida':       f'END ✔ Pedido registado (Ref#{pid})\n{descricao}.',
            'medicamentos': f'END ✔ Pedido registado (Ref#{pid})\nLigue 119 para urgência médica.',
        }
        return msgs[tipo]
    except Exception:
        return 'END Erro ao registar. Ligue 119.'


def _menu_informacoes(partes):
    if len(partes) == 1:
        return (
            'CON INFORMAÇÕES\n'
            '1. Alertas activos\n'
            '2. Números emergência\n'
            '3. Conselhos segurança\n'
            '0. Voltar'
        )

    if partes[1] == '0':
        return _menu_principal()
    if partes[1] == '1':
        return _menu_alertas(['1'])
    if partes[1] == '2':
        return (
            'END EMERGÊNCIA:\n'
            'Polícia:      117\n'
            'Bombeiros:    118\n'
            'SAMU/Saúde:   119\n'
            'Prot.Civil:   26212000\n'
            'Alerta Namp.: 847791199'
        )
    if partes[1] == '3':
        return (
            'END CONSELHOS:\n'
            '• Dirija-se a zonas altas\n'
            '• Evite linhas eléctricas\n'
            '• Não atravesse rios\n'
            '• Guarde documentos\n'
            '• Siga as autoridades\n'
            'Site: alerta-nampula.onrender.com'
        )
    return 'END Opção inválida.'


def _menu_voluntariado(partes, telefone):
    if len(partes) == 1:
        return (
            'CON VOLUNTARIADO\n'
            '1. Registar-me\n'
            '2. Informações doações\n'
            '0. Voltar'
        )

    if partes[1] == '0':
        return _menu_principal()

    if partes[1] == '1':
        if len(partes) == 2:
            return 'CON O seu nome completo:'
        if len(partes) == 3:
            return 'CON As suas habilidades:\n(ex: médico, motorista)'

        nome = partes[2].strip()[:100]
        hab  = partes[3].strip()[:200] if len(partes) > 3 else ''

        if len(nome) < 2:
            return 'END Nome inválido. Tente novamente.'

        existe = query("SELECT id FROM ussd_voluntario WHERE telefone=?", (telefone,), one=True)
        if existe:
            return 'END Já está registado!\nObrigado pelo seu apoio.'

        try:
            query(
                "INSERT INTO ussd_voluntario(nome, telefone, habilidades, data) VALUES(?,?,?,?)",
                (nome, telefone, hab, now_cat()), commit=True
            )
            return f'END ✔ Obrigado, {nome}!\nEntramos em contacto em breve.'
        except Exception:
            return 'END Erro no registo. Tente novamente.'

    if partes[1] == '2':
        return (
            'END DOAÇÕES:\n'
            'M-Pesa Cruz Vermelha: 843\n'
            'M-Pesa INGC: 844\n'
            'Site: alerta-nampula.onrender.com'
        )

    return 'END Opção inválida.'


def _menu_medico(partes, telefone):
    if len(partes) == 1:
        return (
            'CON SUPORTE MÉDICO\n'
            '1. Unidades de saúde\n'
            '2. Pedir ambulância\n'
            '3. Zonas seguras\n'
            '4. Primeiros socorros\n'
            '0. Voltar'
        )

    if partes[1] == '0':
        return _menu_principal()

    if partes[1] == '1':
        return (
            'END UNIDADES DE SAÚDE:\n'
            '• Hospital Central Nampula\n'
            '• CS Napipine\n'
            '• CS Muatala\n'
            '• CS Muhala\n'
            'Emergência: 119'
        )

    if partes[1] == '2':
        try:
            pid = query(
                "INSERT INTO ussd_pedido(telefone, tipo, descricao, data) VALUES(?,?,?,?)",
                (telefone, 'ambulancia', 'Ambulância solicitada via USSD', now_cat()), commit=True
            )
            return (
                f'END ✔ AMBULÂNCIA SOLICITADA! (Ref#{pid})\n'
                'Ligue 119 para confirmar.\n'
                'Informe a sua localização.'
            )
        except Exception:
            return 'END Erro. Ligue 119 directamente.'

    if partes[1] == '3':
        # Lê as zonas do site
        zonas = query("SELECT * FROM zona WHERE ativa=1 ORDER BY nome")
        if not zonas:
            return 'END Sem zonas seguras registadas.\nLigue 119.'
        resp = 'END ZONAS SEGURAS:\n'
        for z in zonas:
            resp += f'• {z["nome"]}\n  Cap: {z["capacidade"]} pessoas\n'
        return resp

    if partes[1] == '4':
        return (
            'END PRIMEIROS SOCORROS:\n'
            'Hemorragia: comprima\n'
            'Inconsciente: deite de lado\n'
            'Afogado: RCP imediato\n'
            'Queimadura: água fria\n'
            'Sempre ligue 119'
        )

    return 'END Opção inválida.'


# ═══════════════════════════════════════════════════════════════
#  API — dados para o admin ver pedidos e voluntários do USSD
# ═══════════════════════════════════════════════════════════════

@app.route('/api/ussd/pedidos')
@login_required
def api_ussd_pedidos():
    pedidos = query("SELECT * FROM ussd_pedido ORDER BY data DESC LIMIT 200")
    return jsonify([dict(p) for p in pedidos])

@app.route('/api/ussd/pedido/<int:pid>/status', methods=['POST'])
@login_required
def api_ussd_pedido_status(pid):
    status = request.json.get('status', '')
    validos = ['pendente', 'em curso', 'concluido', 'cancelado']
    if status not in validos:
        return jsonify({'ok': False}), 400
    query("UPDATE ussd_pedido SET status=? WHERE id=?", (status, pid), commit=True)
    return jsonify({'ok': True})

@app.route('/api/ussd/voluntarios')
@login_required
def api_ussd_voluntarios():
    vols = query("SELECT * FROM ussd_voluntario ORDER BY data DESC")
    return jsonify([dict(v) for v in vols])


# ═══════════════════════════════════════════════════════════════
#  ROTAS PÚBLICAS
# ═══════════════════════════════════════════════════════════════

@app.route('/')
def index():
    alertas  = query("SELECT * FROM alerta WHERE ativo=1 ORDER BY data DESC")
    familias = query("SELECT * FROM familia ORDER BY data DESC")
    zonas    = query("SELECT * FROM zona WHERE ativa=1")
    total    = query("SELECT SUM(numero) s FROM familia", one=True)['s'] or 0
    stats    = {'alertas': len(alertas), 'familias': total, 'zonas': len(zonas),
                'subscricoes': query("SELECT COUNT(*) c FROM subscricao", one=True)['c']}
    cfg = get_site_config()
    return render_template('index.html', alertas=alertas, familias=familias,
                           zonas=zonas, stats=stats, cfg=cfg,
                           fmt_date=fmt_date, fmt_datetime=fmt_datetime)

@app.route('/api/dados_publicos')
def dados_publicos():
    alertas  = query("SELECT * FROM alerta WHERE ativo=1 ORDER BY data DESC")
    familias = query("SELECT * FROM familia ORDER BY data DESC")
    zonas    = query("SELECT * FROM zona WHERE ativa=1")
    total    = query("SELECT SUM(numero) s FROM familia", one=True)['s'] or 0
    stats    = {
        'alertas':     len(alertas),
        'familias':    total,
        'zonas':       len(zonas),
        'subscricoes': query("SELECT COUNT(*) c FROM subscricao", one=True)['c']
    }

    def row_to_dict(row):
        return {key: row[key] for key in row.keys()}

    return jsonify({
        'alertas':  [row_to_dict(a) for a in alertas],
        'familias': [row_to_dict(f) for f in familias],
        'zonas':    [row_to_dict(z) for z in zonas],
        'stats':    stats
    })

@app.route('/apoio', methods=['POST'])
def apoio():
    try:
        query("INSERT INTO apoio(tipo,quantidade,local_entrega,contacto,status,data) VALUES(?,?,?,?,?,?)",
              (request.form.get('tipo_apoio',''), request.form.get('quantidade',''),
               request.form.get('local_entrega',''), request.form.get('contacto',''),
               'pendente', now_cat()), commit=True)
        return jsonify({'ok': True, 'msg': 'Obrigado pelo seu apoio!'})
    except Exception as e:
        return jsonify({'ok': False, 'msg': str(e)})

@app.route('/subscricao', methods=['POST'])
def subscricao():
    try:
        telefone = request.form.get('telefone', '').strip()
        email    = request.form.get('email', '').strip()

        if telefone:
            existente = query("SELECT id FROM subscricao WHERE telefone=?", (telefone,), one=True)
            if existente:
                return jsonify({'ok': False, 'msg': 'Este número já está registado.'})
        if email:
            existente = query("SELECT id FROM subscricao WHERE email=?", (email,), one=True)
            if existente:
                return jsonify({'ok': False, 'msg': 'Este email já está registado.'})

        query("INSERT INTO subscricao(nome,telefone,email,metodos,tipo_alertas,data) VALUES(?,?,?,?,?,?)",
              (request.form.get('nome',''), telefone, email,
               ', '.join(request.form.getlist('notificacoes[]')),
               ', '.join(request.form.getlist('tipo_alertas[]')),
               now_cat()), commit=True)
        return jsonify({'ok': True, 'msg': 'Subscrição activada com sucesso!'})
    except Exception as e:
        return jsonify({'ok': False, 'msg': str(e)})


# ═══════════════════════════════════════════════════════════════
#  AUTH
# ═══════════════════════════════════════════════════════════════

@app.route('/login', methods=['GET','POST'])
def login():
    if session.get('admin_id'):
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        email = request.form.get('email','').strip()
        pwd   = request.form.get('password','').strip()
        adm   = query("SELECT * FROM admin WHERE email=? AND password=?", (email, pwd), one=True)
        if adm:
            session['admin_id']    = adm['id']
            session['admin_nome']  = adm['nome']
            session['admin_nivel'] = adm['nivel']
            return redirect(url_for('admin_dashboard'))
        flash('Email ou palavra-passe incorrectos.', 'error')
    return render_template('login.html', cfg=get_site_config())

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# ═══════════════════════════════════════════════════════════════
#  ADMIN DASHBOARD
# ═══════════════════════════════════════════════════════════════

@app.route('/admin')
@login_required
def admin_dashboard():
    cfg         = get_site_config()
    familias    = query("SELECT * FROM familia ORDER BY data DESC")
    alertas     = query("SELECT * FROM alerta ORDER BY data DESC")
    zonas       = query("SELECT * FROM zona ORDER BY id DESC")
    apoios      = query("SELECT * FROM apoio ORDER BY data DESC")
    subscricoes = query("SELECT * FROM subscricao ORDER BY data DESC")
    admins      = query("SELECT * FROM admin ORDER BY nivel DESC, nome ASC") if session.get('admin_nivel') == 'master' else []

    # Pedidos e voluntários do USSD
    ussd_pedidos    = query("SELECT * FROM ussd_pedido ORDER BY data DESC LIMIT 50")
    ussd_voluntarios = query("SELECT * FROM ussd_voluntario ORDER BY data DESC")

    total       = query("SELECT SUM(numero) s FROM familia", one=True)['s'] or 0
    cap_total   = query("SELECT SUM(capacidade) s FROM zona WHERE ativa=1", one=True)['s'] or 0
    pendentes   = query("SELECT COUNT(*) c FROM apoio WHERE status='pendente' OR status IS NULL", one=True)['c']
    ussd_pend   = query("SELECT COUNT(*) c FROM ussd_pedido WHERE status='pendente'", one=True)['c']

    stats = {
        'alertas':              query("SELECT COUNT(*) c FROM alerta", one=True)['c'],
        'alertas_ativos':       query("SELECT COUNT(*) c FROM alerta WHERE ativo=1", one=True)['c'],
        'alertas_urgentes':     query("SELECT COUNT(*) c FROM alerta WHERE tipo='urgente' AND ativo=1", one=True)['c'],
        'familias_registadas':  len(familias),
        'familias_total':       total,
        'zonas':                query("SELECT COUNT(*) c FROM zona WHERE ativa=1", one=True)['c'],
        'cap_total':            cap_total,
        'apoios':               query("SELECT COUNT(*) c FROM apoio", one=True)['c'],
        'apoios_semana':        query("SELECT COUNT(*) c FROM apoio WHERE data >= datetime('now','-7 days')", one=True)['c'],
        'apoios_pendentes':     pendentes,
        'subscricoes':          query("SELECT COUNT(*) c FROM subscricao", one=True)['c'],
        'subs_mes':             query("SELECT COUNT(*) c FROM subscricao WHERE data >= datetime('now','-30 days')", one=True)['c'],
        'admins':               query("SELECT COUNT(*) c FROM admin", one=True)['c'],
        'ussd_pedidos_total':   query("SELECT COUNT(*) c FROM ussd_pedido", one=True)['c'],
        'ussd_pedidos_pend':    ussd_pend,
        'ussd_voluntarios':     query("SELECT COUNT(*) c FROM ussd_voluntario", one=True)['c'],
    }

    active_tab = request.args.get('tab', 'dashboard')
    return render_template('admin.html', cfg=cfg, stats=stats, alertas=alertas,
                           familias=familias, zonas=zonas, apoios=apoios,
                           subscricoes=subscricoes, admins=admins,
                           ussd_pedidos=ussd_pedidos,
                           ussd_voluntarios=ussd_voluntarios,
                           fmt_date=fmt_date, fmt_datetime=fmt_datetime,
                           active_tab=active_tab)


# ═══════════════════════════════════════════════════════════════
#  ADMIN — ALERTAS
# ═══════════════════════════════════════════════════════════════

@app.route('/admin/alerta/add', methods=['POST'])
@login_required
def add_alerta():
    query("INSERT INTO alerta(titulo,tipo,conteudo,data) VALUES(?,?,?,?)",
          (request.form['titulo'], request.form['tipo'], request.form['conteudo'], now_cat()), commit=True)
    flash('Alerta publicado! Já está visível no site e no USSD.', 'success')
    return redirect(url_for('admin_dashboard', tab='tab-alertas'))

@app.route('/admin/alerta/editar/<int:id>', methods=['GET','POST'])
@login_required
def editar_alerta(id):
    alerta = query("SELECT * FROM alerta WHERE id=?", (id,), one=True)
    if not alerta:
        flash('Alerta não encontrado.', 'error')
        return redirect(url_for('admin_dashboard', tab='tab-alertas'))
    if request.method == 'POST':
        query("UPDATE alerta SET titulo=?, tipo=?, conteudo=?, data=?, ativo=1 WHERE id=?",
              (request.form['titulo'], request.form['tipo'], request.form['conteudo'], now_cat(), id), commit=True)
        flash('Alerta actualizado — visível no site e USSD.', 'success')
        return redirect(url_for('admin_dashboard', tab='tab-alertas'))
    cfg = get_site_config()
    return render_template('editar_alerta.html', alerta=alerta, cfg=cfg)

@app.route('/admin/alerta/toggle/<int:id>')
@login_required
def toggle_alerta(id):
    query("UPDATE alerta SET ativo=CASE WHEN ativo=1 THEN 0 ELSE 1 END WHERE id=?", (id,), commit=True)
    return redirect(url_for('admin_dashboard', tab='tab-alertas'))

@app.route('/admin/alerta/delete/<int:id>')
@login_required
def delete_alerta(id):
    query("DELETE FROM alerta WHERE id=?", (id,), commit=True)
    flash('Alerta eliminado.', 'success')
    return redirect(url_for('admin_dashboard', tab='tab-alertas'))


# ═══════════════════════════════════════════════════════════════
#  ADMIN — FAMÍLIAS
# ═══════════════════════════════════════════════════════════════

@app.route('/admin/familia/add', methods=['POST'])
@login_required
def add_familia():
    query("INSERT INTO familia(bairro,numero,situacao,abrigo,necessidades,data) VALUES(?,?,?,?,?,?)",
          (request.form['bairro'], int(request.form['numero']), request.form['situacao'],
           request.form['abrigo'], request.form['necessidades'], now_cat()), commit=True)
    flash('Família registada!', 'success')
    return redirect(url_for('admin_dashboard', tab='tab-familias'))

@app.route('/admin/familia/editar/<int:id>', methods=['GET','POST'])
@login_required
def editar_familia(id):
    familia = query("SELECT * FROM familia WHERE id=?", (id,), one=True)
    if not familia:
        flash('Família não encontrada.', 'error')
        return redirect(url_for('admin_dashboard', tab='tab-familias'))
    if request.method == 'POST':
        query("UPDATE familia SET bairro=?, numero=?, situacao=?, abrigo=?, necessidades=?, data=? WHERE id=?",
              (request.form['bairro'], int(request.form['numero']), request.form['situacao'],
               request.form['abrigo'], request.form['necessidades'], now_cat(), id), commit=True)
        flash('Família actualizada!', 'success')
        return redirect(url_for('admin_dashboard', tab='tab-familias'))
    cfg = get_site_config()
    return render_template('editar_familia.html', familia=familia, cfg=cfg)

@app.route('/admin/familia/delete/<int:id>')
@login_required
def delete_familia(id):
    query("DELETE FROM familia WHERE id=?", (id,), commit=True)
    flash('Família eliminada.', 'success')
    return redirect(url_for('admin_dashboard', tab='tab-familias'))


# ═══════════════════════════════════════════════════════════════
#  ADMIN — ZONAS
# ═══════════════════════════════════════════════════════════════

@app.route('/admin/zona/add', methods=['POST'])
@login_required
def add_zona():
    query("INSERT INTO zona(nome,capacidade,recursos) VALUES(?,?,?)",
          (request.form['nome'], int(request.form['capacidade']), request.form['recursos']), commit=True)
    flash('Zona segura adicionada!', 'success')
    return redirect(url_for('admin_dashboard', tab='tab-zonas'))

@app.route('/admin/zona/editar/<int:id>', methods=['GET','POST'])
@login_required
def editar_zona(id):
    zona = query("SELECT * FROM zona WHERE id=?", (id,), one=True)
    if not zona:
        flash('Zona não encontrada.', 'error')
        return redirect(url_for('admin_dashboard', tab='tab-zonas'))
    if request.method == 'POST':
        query("UPDATE zona SET nome=?, capacidade=?, recursos=? WHERE id=?",
              (request.form['nome'], int(request.form['capacidade']), request.form['recursos'], id), commit=True)
        flash('Zona actualizada!', 'success')
        return redirect(url_for('admin_dashboard', tab='tab-zonas'))
    cfg = get_site_config()
    return render_template('editar_zona.html', zona=zona, cfg=cfg)

@app.route('/admin/zona/toggle/<int:id>')
@login_required
def toggle_zona(id):
    query("UPDATE zona SET ativa=CASE WHEN ativa=1 THEN 0 ELSE 1 END WHERE id=?", (id,), commit=True)
    return redirect(url_for('admin_dashboard', tab='tab-zonas'))

@app.route('/admin/zona/delete/<int:id>')
@login_required
def delete_zona(id):
    query("DELETE FROM zona WHERE id=?", (id,), commit=True)
    flash('Zona eliminada.', 'success')
    return redirect(url_for('admin_dashboard', tab='tab-zonas'))


# ═══════════════════════════════════════════════════════════════
#  ADMIN — APOIOS
# ═══════════════════════════════════════════════════════════════

@app.route('/admin/apoio/confirmar/<int:id>')
@login_required
def confirmar_apoio(id):
    query("UPDATE apoio SET status='confirmado' WHERE id=?", (id,), commit=True)
    flash('Apoio confirmado!', 'success')
    return redirect(url_for('admin_dashboard', tab='tab-apoios'))

@app.route('/admin/apoio/recusar/<int:id>')
@login_required
def recusar_apoio(id):
    query("UPDATE apoio SET status='recusado' WHERE id=?", (id,), commit=True)
    flash('Apoio recusado.', 'success')
    return redirect(url_for('admin_dashboard', tab='tab-apoios'))

@app.route('/admin/apoio/delete/<int:id>')
@login_required
def delete_apoio(id):
    query("DELETE FROM apoio WHERE id=?", (id,), commit=True)
    flash('Apoio eliminado.', 'success')
    return redirect(url_for('admin_dashboard', tab='tab-apoios'))


# ═══════════════════════════════════════════════════════════════
#  ADMIN — PEDIDOS USSD
# ═══════════════════════════════════════════════════════════════

@app.route('/admin/ussd_pedido/status/<int:id>', methods=['POST'])
@login_required
def update_ussd_pedido(id):
    status = request.form.get('status', 'pendente')
    query("UPDATE ussd_pedido SET status=? WHERE id=?", (status, id), commit=True)
    flash('Estado actualizado!', 'success')
    return redirect(url_for('admin_dashboard', tab='tab-ussd'))

@app.route('/admin/ussd_pedido/delete/<int:id>')
@login_required
def delete_ussd_pedido(id):
    query("DELETE FROM ussd_pedido WHERE id=?", (id,), commit=True)
    flash('Pedido eliminado.', 'success')
    return redirect(url_for('admin_dashboard', tab='tab-ussd'))


# ═══════════════════════════════════════════════════════════════
#  ADMIN — CONFIG
# ═══════════════════════════════════════════════════════════════

@app.route('/admin/config/update', methods=['POST'])
@master_required
def update_config():
    for campo in ['site_nome','site_subtitulo','site_email','site_telefone',
                  'site_endereco','site_whatsapp','site_facebook','site_twitter']:
        query("UPDATE configuracao SET valor=? WHERE chave=?",
              (request.form.get(campo,''), campo), commit=True)
    flash('Configurações actualizadas!', 'success')
    return redirect(url_for('admin_dashboard', tab='tab-config'))


# ═══════════════════════════════════════════════════════════════
#  ADMIN — UTILIZADORES
# ═══════════════════════════════════════════════════════════════

@app.route('/admin/admin_user/add', methods=['POST'])
@master_required
def add_admin_user():
    try:
        query("INSERT INTO admin(nome,email,password,nivel) VALUES(?,?,?,?)",
              (request.form['nome'], request.form['email'],
               request.form['password'], request.form['nivel']), commit=True)
        flash('Administrador criado!', 'success')
    except:
        flash('Email já existe no sistema.', 'error')
    return redirect(url_for('admin_dashboard', tab='tab-admins'))

@app.route('/admin/admin_user/delete/<int:id>')
@master_required
def delete_admin_user(id):
    if id == session.get('admin_id'):
        flash('Não pode eliminar a sua própria conta.', 'error')
        return redirect(url_for('admin_dashboard', tab='tab-admins'))
    query("DELETE FROM admin WHERE id=?", (id,), commit=True)
    flash('Administrador eliminado.', 'success')
    return redirect(url_for('admin_dashboard', tab='tab-admins'))


# ═══════════════════════════════════════════════════════════════
#  BACKUP
# ═══════════════════════════════════════════════════════════════

@app.route('/cron/backup_auto')
def backup_auto():
    import shutil
    CHAVE_SECRETA = 'AlertaN4mpul4@2026!'
    if request.args.get('chave') != CHAVE_SECRETA:
        return 'Erro: Chave inválida', 403
    try:
        if not os.path.exists('backups'):
            os.makedirs('backups')
        agora = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f'backups/backup_{agora}.db'
        if os.path.exists('alerta.db'):
            shutil.copy('alerta.db', backup_file)
        else:
            return 'Erro: alerta.db não encontrado', 404
        backups = sorted([f for f in os.listdir('backups') if f.endswith('.db')])
        while len(backups) > 30:
            os.remove(os.path.join('backups', backups.pop(0)))
        return f'✅ Backup criado: backup_{agora}.db'
    except Exception as e:
        return f'❌ Erro: {str(e)}', 500

@app.route('/admin/backups')
@login_required
def listar_backups():
    if not os.path.exists('backups'):
        return 'Nenhum backup encontrado'
    backups = sorted([f for f in os.listdir('backups') if f.endswith('.db')], reverse=True)
    from jinja2 import Template
    html = '<h1>Backups</h1><ul>{% for b in backups %}<li><a href="/admin/backup/{{ b }}">{{ b }}</a></li>{% endfor %}</ul><p><a href="/admin">← Voltar</a></p>'
    return Template(html).render(backups=backups)

@app.route('/admin/backup/<nome>')
@login_required
def baixar_backup(nome):
    from flask import send_file
    if '..' in nome or not nome.startswith('backup_'):
        return 'Ficheiro inválido', 400
    caminho = os.path.join('backups', nome)
    if not os.path.exists(caminho):
        return 'Backup não encontrado', 404
    return send_file(caminho, as_attachment=True)


# ═══════════════════════════════════════════════════════════════
#  UTILITÁRIOS
# ═══════════════════════════════════════════════════════════════

@app.route('/ping')
def ping():
    return 'pong', 200


# ═══════════════════════════════════════════════════════════════
#  ARRANQUE CORRECTO PARA RENDER
# ═══════════════════════════════════════════════════════════════

# Inicializa a base de dados (executado apenas uma vez)
with app.app_context():
    init_db()

# ✅ EXPORTA a aplicação para o Gunicorn (Render)
application = app

# PARA TESTES LOCAIS APENAS
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
