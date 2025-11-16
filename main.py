# main.py
import functions_framework

# Registriert eine HTTP-Funktion mit dem Namen 'python_function_template'
@functions_framework.http
def python_function_template(request):
  """
  Eine einfache, HTTP-getriggerte Cloud Function.
  Nimmt den Namen aus dem Query-Parameter oder setzt einen Standardwert.
  """
  name = request.args.get("name", "Unbekannter")
  
  print(f"Funktion wurde mit dem Namen '{name}' aufgerufen.") # Fürs Logging
  
  return f"Hallo, {name}, aus einer Python Cloud Function!"
