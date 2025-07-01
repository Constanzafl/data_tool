# 🔍 Schema Analyzer - Detector de Relaciones y Generador de Diagramas ER

Herramienta completa para analizar esquemas de bases de datos, detectar relaciones automáticamente y generar diagramas ER usando DBML.

## 🚀 Instalación Rápida

### 1. Crear entorno virtual
```bash
python -m venv schema_analyzer_env
source schema_analyzer_env/bin/activate  # Linux/Mac
# o
schema_analyzer_env\Scripts\activate  # Windows
```

### 2. Instalar dependencias
```bash
pip install pandas numpy scikit-learn sentence-transformers psycopg2-binary requests tqdm python-dotenv
```

### 3. (Opcional) Instalar Ollama para verificación con LLM
```bash
# MacOS/Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows: Descargar desde https://ollama.ai/download

# Iniciar servidor
ollama serve

# Instalar un modelo (elige uno)
ollama pull llama2      # Recomendado, 3.8GB
ollama pull mistral     # Más potente, 4.1GB
ollama pull phi         # Más liviano, 1.6GB
```

## 📁 Estructura de Archivos

```
schema_analyzer/
├── schema_extractor.py      # Fase 1: Extrae esquema de BD
├── relationship_detector.py  # Fase 2: Detecta relaciones con embeddings
├── llm_verifier.py          # Fase 3: Verifica con LLM local
├── dbml_generator.py        # Fase 4: Genera código DBML
├── complete_schema_analyzer.py  # Fase 5: Integración completa
└── requirements.txt         # Dependencias
```

## 🎯 Uso Básico

### Ejemplo con SQLite:
```python
from complete_schema_analyzer import SchemaAnalyzer

# Crear analizador
analyzer = SchemaAnalyzer(
    db_type="sqlite",
    connection_params={"database": "tu_database.db"},
    use_llm=True  # False si no tienes Ollama
)

# Ejecutar análisis completo
results = analyzer.analyze_complete(
    output_dir="./output",
    sample_size=5,
    max_llm_verifications=10
)
```

### Ejemplo con PostgreSQL:
```python
analyzer = SchemaAnalyzer(
    db_type="postgresql",
    connection_params={
        "host": "localhost",
        "database": "mydb",
        "user": "user",
        "password": "password",
        "port": 5432
    },
    use_llm=True
)
```

## 📊 Qué hace cada fase:

### Fase 1: Extracción de Esquema
- Conecta a tu base de datos
- Extrae todas las tablas, columnas, tipos
- Identifica PKs y FKs existentes
- Cuenta filas por tabla

### Fase 2: Detección de Relaciones
- Analiza nombres de columnas (patrones como _id, _fk)
- Usa embeddings para encontrar similitudes semánticas
- Detecta posibles relaciones no documentadas
- Asigna puntuación de confianza

### Fase 3: Verificación con LLM (Opcional)
- Usa Ollama (LLM local gratuito)
- Verifica las relaciones detectadas
- Explica por qué son válidas o no
- Determina cardinalidad (1:1, 1:N, etc.)

### Fase 4: Generación DBML
- Convierte el esquema a código DBML
- Incluye todas las relaciones (existentes + detectadas)
- Agrega notas y metadatos
- Agrupa tablas automáticamente

### Fase 5: Integración
- Ejecuta todo el pipeline
- Genera reportes detallados
- Guarda todos los resultados
- Proporciona instrucciones para visualizar

## 🎨 Visualizar el Diagrama ER

1. Abre el archivo `.dbml` generado en `output/`
2. Copia todo el contenido
3. Ve a [dbdiagram.io](https://dbdiagram.io/d)
4. Pega el código en el editor
5. ¡Disfruta tu diagrama ER interactivo!

## 🛠️ Configuración Avanzada

### Sin LLM (solo embeddings):
```python
analyzer = SchemaAnalyzer(
    db_type="sqlite",
    connection_params={"database": "db.sqlite"},
    use_llm=False  # Solo usa embeddings
)
```

### Personalizar detección:
```python
# Después de crear el analyzer
analyzer.detector.common_fk_patterns.append(r'_foreign$')
analyzer.detector.common_pk_patterns.append(r'^identifier$')
```

### Generar solo DBML sin análisis:
```python
from dbml_generator import DBMLGenerator

generator = DBMLGenerator()
dbml_code = generator.generate_dbml(
    schema,  # Tu diccionario de esquema
    relationships,  # Lista de relaciones
    project_name="Mi Proyecto"
)
```

## 🐛 Solución de Problemas

### "No se puede conectar con Ollama"
1. Verifica que Ollama esté instalado: `ollama --version`
2. Inicia el servidor: `ollama serve`
3. O usa `use_llm=False` para saltar verificación LLM

### "No se puede conectar a la base de datos"
- SQLite: Verifica que el archivo .db existe
- PostgreSQL: Verifica credenciales y que el servidor esté corriendo

### "Error en embeddings"
- Asegúrate de tener instalado `sentence-transformers`
- Primera ejecución descarga el modelo (~400MB)

## 📈 Mejoras Futuras

- [ ] Soporte para MySQL/MariaDB
- [ ] Detección de relaciones N:M
- [ ] Exportación a SQL
- [ ] API REST
- [ ] Interfaz web
- [ ] Más modelos de embeddings

## 🤝 Contribuir

¡Las contribuciones son bienvenidas! Por favor:
1. Fork el proyecto
2. Crea tu rama (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📝 Licencia

Este proyecto es de código abierto bajo licencia MIT.