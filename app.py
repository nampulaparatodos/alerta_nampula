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
    """Return current datetime string in Mozambique time (CAT = UTC+2)"""
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
                ('Alerta Meteorológico','urgente','Previsão de chuvas fortes nos próximos 3 dias.', now_cat()),
                ('Segurança Pública','atencao','Atenção redobrada em locais públicos.', now_cat()),
                ('Saúde Pública','informativo','Campanha de vacinação contra a cólera.', now_cat()),
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

# ─── PUBLIC ───────────────────────────────────────────────────────────────────

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
    alertas = query("SELECT * FROM alerta WHERE ativo=1 ORDER BY data DESC")
    familias = query("SELECT * FROM familia ORDER BY data DESC")
    zonas = query("SELECT * FROM zona WHERE ativa=1")
    total = query("SELECT SUM(numero) s FROM familia", one=True)['s'] or 0
    stats = {
        'alertas': len(alertas),
        'familias': total,
        'zonas': len(zonas),
        'subscricoes': query("SELECT COUNT(*) c FROM subscricao", one=True)['c']
    }

    # Converter as linhas (sqlite3.Row) para dicionários comuns
    def row_to_dict(row):
        return {key: row[key] for key in row.keys()}

    return jsonify({
        'alertas': [row_to_dict(a) for a in alertas],
        'familias': [row_to_dict(f) for f in familias],
        'zonas': [row_to_dict(z) for z in zonas],
        'stats': stats
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
        email = request.form.get('email', '').strip()

        # Verificar se já existe registo com o mesmo telefone OU email
        if telefone:
            existente = query("SELECT id FROM subscricao WHERE telefone = ?", (telefone,), one=True)
            if existente:
                return jsonify({'ok': False, 'msg': 'Este número de telemóvel já está registado para notificações.'})
        if email:
            existente = query("SELECT id FROM subscricao WHERE email = ?", (email,), one=True)
            if existente:
                return jsonify({'ok': False, 'msg': 'Este email já está registado para notificações.'})

        # Inserir nova subscrição
        query("INSERT INTO subscricao(nome,telefone,email,metodos,tipo_alertas,data) VALUES(?,?,?,?,?,?)",
              (request.form.get('nome',''), telefone, email,
               ', '.join(request.form.getlist('notificacoes[]')),
               ', '.join(request.form.getlist('tipo_alertas[]')),
               now_cat()), commit=True)
        return jsonify({'ok': True, 'msg': 'Subscrição activada com sucesso!'})
    except Exception as e:
        return jsonify({'ok': False, 'msg': str(e)})

# ─── AUTH ─────────────────────────────────────────────────────────────────────

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

# ─── ADMIN DASHBOARD ──────────────────────────────────────────────────────────

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

    total       = query("SELECT SUM(numero) s FROM familia", one=True)['s'] or 0
    cap_total   = query("SELECT SUM(capacidade) s FROM zona WHERE ativa=1", one=True)['s'] or 0
    pendentes   = query("SELECT COUNT(*) c FROM apoio WHERE status='pendente' OR status IS NULL", one=True)['c']

    stats = {
        'alertas':           query("SELECT COUNT(*) c FROM alerta", one=True)['c'],
        'alertas_ativos':    query("SELECT COUNT(*) c FROM alerta WHERE ativo=1", one=True)['c'],
        'alertas_urgentes':  query("SELECT COUNT(*) c FROM alerta WHERE tipo='urgente' AND ativo=1", one=True)['c'],
        'familias_registadas': len(familias),
        'familias_total':    total,
        'zonas':             query("SELECT COUNT(*) c FROM zona WHERE ativa=1", one=True)['c'],
        'cap_total':         cap_total,
        'apoios':            query("SELECT COUNT(*) c FROM apoio", one=True)['c'],
        'apoios_semana':     query("SELECT COUNT(*) c FROM apoio WHERE data >= datetime('now','-7 days')", one=True)['c'],
        'apoios_pendentes':  pendentes,
        'subscricoes':       query("SELECT COUNT(*) c FROM subscricao", one=True)['c'],
        'subs_mes':          query("SELECT COUNT(*) c FROM subscricao WHERE data >= datetime('now','-30 days')", one=True)['c'],
        'admins':            query("SELECT COUNT(*) c FROM admin", one=True)['c'],
    }
    active_tab = request.args.get('tab', 'dashboard')
    return render_template('admin.html', cfg=cfg, stats=stats, alertas=alertas,
                           familias=familias, zonas=zonas, apoios=apoios,
                           subscricoes=subscricoes, admins=admins,
                           fmt_date=fmt_date, fmt_datetime=fmt_datetime,
                           active_tab=active_tab)

# ─── ALERTAS ──────────────────────────────────────────────────────────────────

@app.route('/admin/alerta/add', methods=['POST'])
@login_required
def add_alerta():
    query("INSERT INTO alerta(titulo,tipo,conteudo,data) VALUES(?,?,?,?)",
          (request.form['titulo'], request.form['tipo'], request.form['conteudo'], now_cat()), commit=True)
    flash('Alerta publicado!', 'success')
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
        flash('Alerta republicado com sucesso!', 'success')
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

# ─── FAMÍLIAS ─────────────────────────────────────────────────────────────────

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
        flash('Família actualizada e republicada!', 'success')
        return redirect(url_for('admin_dashboard', tab='tab-familias'))
    cfg = get_site_config()
    return render_template('editar_familia.html', familia=familia, cfg=cfg)

@app.route('/admin/familia/delete/<int:id>')
@login_required
def delete_familia(id):
    query("DELETE FROM familia WHERE id=?", (id,), commit=True)
    flash('Família eliminada.', 'success')
    return redirect(url_for('admin_dashboard', tab='tab-familias'))

# ─── ZONAS ────────────────────────────────────────────────────────────────────

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
        flash('Zona segura actualizada!', 'success')
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

# ─── APOIOS ───────────────────────────────────────────────────────────────────

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

# ─── CONFIG ───────────────────────────────────────────────────────────────────

@app.route('/admin/config/update', methods=['POST'])
@master_required
def update_config():
    for campo in ['site_nome','site_subtitulo','site_email','site_telefone',
                  'site_endereco','site_whatsapp','site_facebook','site_twitter']:
        query("UPDATE configuracao SET valor=? WHERE chave=?",
              (request.form.get(campo,''), campo), commit=True)
    flash('Configurações actualizadas!', 'success')
    return redirect(url_for('admin_dashboard', tab='tab-config'))

# ─── ADMIN USERS ──────────────────────────────────────────────────────────────

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

# ─── ROTA DE TESTE PARA VERIFICAR SE O SERVIDOR ESTÁ VIVO ────────────────────

@app.route('/ping')
def ping():
    return "pong", 200

# ─── CONFIGURAÇÃO PARA O RENDER ─────────────────────────────────

if __name__ == '__main__':
    # Modo desenvolvimento (local)
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
else:
    # Modo produção (Render)
    application = app  # LINHA CRÍTICA PARA O RENDER
    # O Render usa a variável de ambiente PORT
