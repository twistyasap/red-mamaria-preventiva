# prevencion/ia_service.py
from poe_api_wrapper import PoeApi

# Pega tus tokens copiados entre las comillas
POE_P_B = "QpVOxX3ej42CMOk72DnmXg%3D%3D"
POE_P_LAT = "rcn+vV58d32L8eEFkC82edIo/a2t5takPWDatpjyAQ=="

def responder_consulta_medica(prompt_usuario, nombre_bot="Assistant"):
    """
    Envía la consulta del usuario a Poe y retorna la respuesta.
    """
    try:
        client = PoeApi(tokens={"p-b": POE_P_B, "p-lat": POE_P_LAT})
        
        respuesta_texto = ""
        for chunk in client.send_message(bot=nombre_bot, message=prompt_usuario):
            respuesta_texto += chunk["response"]
            
        return respuesta_texto

    except Exception as e:
        print(f"Error en la conexión con Poe: {e}")
        return "Lo sentimos, ocurrió un problema técnico al comunicarse con la IA."