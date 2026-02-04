import os
import json
import traceback
from flask import Flask, render_template, request, jsonify
from google import genai
from google.genai import types
from google.genai.errors import ClientError

app = Flask(__name__)
HISTORY_FILE = 'historial.json'

# --- FUNCIONES DE BASE DE DATOS (ARCHIVO) ---
def cargar_historial_db():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []

def guardar_en_historial_db(tema, nivel, contenido):
    historial = cargar_historial_db()
    
    # Creamos el nuevo registro
    nuevo_item = {
        "tema": tema,
        "nivel": nivel,
        "contenido": contenido
    }
    
    # Lo insertamos AL PRINCIPIO de la lista
    historial.insert(0, nuevo_item)
    
    # Guardamos en el archivo
    try:
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(historial, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error guardando historial: {e}")

# --- IA ---
def obtener_contenido_gemini(api_key_usuario, tema, nivel):
    print(f"--- Solicitud API: {tema} [{nivel}] ---")
    try:
        client = genai.Client(api_key=api_key_usuario)
        model = "gemini-2.0-flash" 
        
        instruccion = ""
        if nivel == "Textos":
            instruccion = "Genera párrafos cortos (3-4 oraciones) con continuidad y sentido."
        elif nivel == "Frases":
            instruccion = "Genera oraciones completas y útiles (7-15 palabras)."
        else:
            instruccion = "Genera palabras sueltas con su artículo."

        prompt = f"""
        Profesor de francés. Tema: '{tema}'. Nivel: '{nivel}'. {instruccion}
        Requisito: Incluye 'pronunciacion' aproximada para hispanohablantes.
        Responde SOLO JSON válido:
        [ {{"frances": "...", "pronunciacion": "...", "espanol": "..."}} ]
        """

        response = client.models.generate_content(
            model=model,
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=prompt)])],
            config=types.GenerateContentConfig(temperature=0.7, response_mime_type="application/json")
        )
        
        texto = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(texto)

    except ClientError as e:
        if "403" in str(e) or "INVALID" in str(e): return {"error_code": "KEY", "msg": "Clave inválida."}
        if "429" in str(e): return {"error_code": "QUOTA", "msg": "Cuota agotada."}
        return None
    except Exception:
        return None

# --- RUTAS ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/obtener_historial', methods=['GET'])
def get_historial():
    # Esta ruta permite al frontend descargar la lista guardada
    data = cargar_historial_db()
    return jsonify(data)

@app.route('/generar', methods=['POST'])
def generar():
    data = request.json
    tema = data.get('tema')
    nivel = data.get('nivel')
    api_key = data.get('apiKey')

    if not api_key: return jsonify({"error": "Falta API Key"}), 401

    contenido = obtener_contenido_gemini(api_key, tema, nivel)
    
    if contenido is None: return jsonify({"error": "Error de conexión/clave"}), 500
    if isinstance(contenido, dict) and "error_code" in contenido: return jsonify({"error": contenido["msg"]}), 400
    
    # ¡AQUÍ ESTÁ LA MAGIA! Guardamos en el archivo antes de responder
    guardar_en_historial_db(tema, nivel, contenido)
    
    return jsonify(contenido)

if __name__ == '__main__':
    print("--- SERVIDOR CON HISTORIAL PERSISTENTE ---")
    app.run(debug=True, port=5000, host='0.0.0.0')