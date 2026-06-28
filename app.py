import os
from flask import Flask, render_template, request, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# --- CONFIGURACIÓN ---
basedir = os.path.abspath(os.path.dirname(__file__))
app = Flask(__name__)
app.secret_key = 'ruka_urbana_clave_secreta_estatica'

# Almacenamiento
UPLOAD_FOLDER = os.path.join(basedir, 'static/uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Base de Datos
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'ruka.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# --- MODELOS ---
class Usuario(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)

class Propiedad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    precio = db.Column(db.Integer, nullable=False)  # 👈 CAMBIO AQUÍ
    operacion = db.Column(db.String(20))
    tipo = db.Column(db.String(50))
    imagen_url = db.Column(db.String(255))
    habitaciones = db.Column(db.Integer, default=0)
    banos = db.Column(db.Integer, default=0)
    superficie = db.Column(db.Integer, default=0)
    estacionamientos = db.Column(db.Integer, default=0)
    ubicacion = db.Column(db.String(200))
    imagenes = db.relationship('ImagenPropiedad', backref='propiedad', lazy=True, cascade="all, delete-orphan")

class ImagenPropiedad(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ruta = db.Column(db.String(255), nullable=False)
    propiedad_id = db.Column(db.Integer, db.ForeignKey('propiedad.id'), nullable=False)

# --- LOGIN MANAGER ---
login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))

# --- FUNCIONES DE APOYO ---
def guardar_imagen_local(archivo):
    if not archivo or archivo.filename == '':
        return None
    try:
        nombre_archivo = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secure_filename(archivo.filename)}"
        ruta_completa = os.path.join(app.config['UPLOAD_FOLDER'], nombre_archivo)
        archivo.save(ruta_completa)
        return f"uploads/{nombre_archivo}"
    except Exception:
        return None

def borrar_archivo_fisico(ruta_relativa):
    """Elimina el archivo físico de la carpeta static si existe"""
    if ruta_relativa:
        # Construye la ruta absoluta
        ruta_completa = os.path.join(basedir, 'static', ruta_relativa)
        if os.path.exists(ruta_completa):
            try:
                os.remove(ruta_completa)
            except Exception as e:
                print(f"No se pudo borrar el archivo: {e}")

# --- MODELOS ---
# (Aquí van tus clases de Usuario, Propiedad, etc.)

# --- INICIALIZACIÓN FORZADA (Ponlo aquí, antes de las rutas) ---
with app.app_context():
    db.create_all()
    # Crear usuarios si la tabla está vacía
    if not Usuario.query.filter_by(username='Jose').first():
        db.session.add(Usuario(username='Jose', password=generate_password_hash('jose123')))
        db.session.add(Usuario(username='Rodrigo', password=generate_password_hash('rodrigo123')))
        db.session.commit()

# --- RUTAS ---
@app.route('/')
def home():
    operacion = request.args.get('operacion')
    tipo = request.args.get('tipo')
    query = Propiedad.query
    if operacion: query = query.filter(Propiedad.operacion == operacion)
    if tipo: query = query.filter(Propiedad.tipo == tipo)
    propiedades = query.order_by(Propiedad.id.desc()).all()
    return render_template('index.html', propiedades=propiedades)

@app.route('/propiedad/<int:id>')
def detalle_propiedad(id):
    propiedad = db.session.get(Propiedad, id)
    if not propiedad:
        flash("Propiedad no encontrada", "warning")
        return redirect(url_for('home'))
    return render_template('detalle.html', propiedad=propiedad)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = Usuario.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            login_user(user)
            return redirect(url_for('admin'))
        flash("Usuario o contraseña incorrectos", "danger")
    return render_template('login.html')

@app.route('/admin')
@login_required
def admin():
    propiedades = Propiedad.query.all()
    return render_template('admin.html', propiedades=propiedades)

@app.route('/admin/add_propiedad', methods=['POST'])
@login_required
def add_propiedad():
    try:
        file_portada = request.files.get('imagen_archivo')
        imagen_url = guardar_imagen_local(file_portada) or request.form.get('imagen_url')

        # 👇 LIMPIAR PRECIO AQUÍ
        precio_str = request.form['precio'].replace('.', '')
        precio = int(precio_str)

        nueva_p = Propiedad(
            titulo=request.form.get('titulo'),
            descripcion=request.form.get('descripcion'),
            precio=precio,  # 👈 ahora sí correcto
            imagen_url=imagen_url,
            ubicacion=request.form.get('ubicacion'),
            operacion=request.form.get('operacion'),
            tipo=request.form.get('tipo'),
            habitaciones=int(request.form.get('habitaciones') or 0),
            banos=int(request.form.get('banos') or 0),
            superficie=int(request.form.get('superficie') or 0),
            estacionamientos=int(request.form.get('estacionamientos') or 0)
        )

        db.session.add(nueva_p)
        db.session.flush()
        fotos_galeria = request.files.getlist('galeria_archivos')
        for foto in fotos_galeria:
            ruta_extra = guardar_imagen_local(foto)
            if ruta_extra:
                db.session.add(ImagenPropiedad(ruta=ruta_extra, propiedad_id=nueva_p.id))
        db.session.commit()
        flash("¡Propiedad publicada!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error: {str(e)}", "danger")
    return redirect(url_for('admin'))

@app.route('/admin/delete_propiedad/<int:id>', methods=['POST'])
@login_required
def delete_propiedad(id):
    try:
        propiedad = db.session.get(Propiedad, id)
        if propiedad:
            # 1. Borrar imagen de portada
            borrar_archivo_fisico(propiedad.imagen_url)
            # 2. Borrar imágenes de la galería
            for img in propiedad.imagenes:
                borrar_archivo_fisico(img.ruta)
            # 3. Borrar de la base de datos
            db.session.delete(propiedad)
            db.session.commit()
            flash("Propiedad eliminada correctamente", "success")
        else:
            flash("La propiedad no existe", "danger")
    except Exception as e:
        db.session.rollback()
        flash(f"Error al eliminar: {str(e)}", "danger")
    return redirect(url_for('admin'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

@app.route('/favoritos')
def favoritos():
    return render_template('favoritos.html')

@app.route('/admin/edit_propiedad/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_propiedad(id):
    # Usamos 'propiedad' para que coincida con tu HTML
    propiedad = db.session.get(Propiedad, id)
    if not propiedad:
        flash("Propiedad no encontrada", "danger")
        return redirect(url_for('admin'))

    if request.method == 'POST':
        try:
            propiedad.titulo = request.form.get('titulo')
            propiedad.precio = request.form.get('precio')
            propiedad.operacion = request.form.get('operacion')
            # ... agrega aquí los demás campos si los necesitas ...

            # Manejo de nuevas fotos para la galería
            nuevas_fotos = request.files.getlist('galeria_archivos')
            for foto in nuevas_fotos:
                ruta_extra = guardar_imagen_local(foto)
                if ruta_extra:
                    db.session.add(ImagenPropiedad(ruta=ruta_extra, propiedad_id=propiedad.id))

            db.session.commit()
            flash("Propiedad actualizada", "success")
            return redirect(url_for('admin'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error: {str(e)}", "danger")

    return render_template('edit_propiedad.html', propiedad=propiedad)

# RUTA NUEVA: Para borrar fotos sueltas de la galería
@app.route('/admin/delete_foto/<int:id>', methods=['POST'])
@login_required
def delete_foto(id):
    foto = db.session.get(ImagenPropiedad, id)
    if foto:
        propiedad_id = foto.propiedad_id
        borrar_archivo_fisico(foto.ruta)
        db.session.delete(foto)
        db.session.commit()
        flash("Foto eliminada", "info")
        return redirect(url_for('edit_propiedad', id=propiedad_id))
    return redirect(url_for('admin'))

# --- ARRANQUE ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        for u_name, u_pass in [("Jose", "jose123"), ("Rodrigo", "rodrigo123")]:
            if not Usuario.query.filter_by(username=u_name).first():
                db.session.add(Usuario(username=u_name, password=generate_password_hash(u_pass)))
        db.session.commit()
    app.run(debug=True)