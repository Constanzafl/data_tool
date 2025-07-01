"""
Fase 3: Verificador con LLM Local (Ollama)
Verifica las relaciones detectadas usando un LLM local gratuito
"""

import requests
import json
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import time

@dataclass
class VerifiedRelationship:
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    confidence: float
    llm_confidence: float
    relationship_type: str
    cardinality: str  # "1:1", "1:N", "N:1", "N:M"
    explanation: str
    is_valid: bool

class OllamaVerifier:
    def __init__(self, model: str = "llama2", host: str = "http://localhost:11434"):
        """
        Inicializa el verificador con Ollama
        
        Args:
            model: Modelo a usar (llama2, mistral, codellama, etc.)
            host: URL del servidor Ollama
        """
        self.model = model
        self.host = host
        self.api_url = f"{host}/api/generate"
        
        # Verificar que Ollama está corriendo
        self._check_ollama_connection()
    
    def _check_ollama_connection(self):
        """Verifica que Ollama esté disponible"""
        try:
            response = requests.get(f"{self.host}/api/tags")
            if response.status_code == 200:
                models = response.json().get('models', [])
                print(f"✅ Ollama conectado. Modelos disponibles: {[m['name'] for m in models]}")
                
                # Verificar si el modelo solicitado está disponible
                model_names = [m['name'] for m in models]
                if self.model not in model_names and f"{self.model}:latest" not in model_names:
                    print(f"⚠️  Modelo '{self.model}' no encontrado. Instalando...")
                    self._pull_model(self.model)
            else:
                raise ConnectionError("No se pudo conectar con Ollama")
        except Exception as e:
            print(f"❌ Error: {e}")
            print("ℹ️  Asegúrate de que Ollama esté instalado y corriendo:")
            print("    1. Instala Ollama: https://ollama.ai")
            print("    2. Ejecuta: ollama serve")
            print("    3. Instala un modelo: ollama pull llama2")
            raise
    
    def _pull_model(self, model_name: str):
        """Descarga un modelo si no está disponible"""
        print(f"Descargando modelo {model_name}...")
        response = requests.post(
            f"{self.host}/api/pull",
            json={"name": model_name}
        )
        if response.status_code == 200:
            print(f"✅ Modelo {model_name} instalado exitosamente")
        else:
            print(f"❌ Error al instalar modelo: {response.text}")
    
    def verify_relationship(self, 
                          relationship: 'RelationshipCandidate',
                          source_table_info: Dict,
                          target_table_info: Dict,
                          sample_data: Optional[Dict] = None) -> VerifiedRelationship:
        """
        Verifica una relación usando el LLM
        
        Args:
            relationship: Candidato de relación a verificar
            source_table_info: Información de la tabla origen
            target_table_info: Información de la tabla destino
            sample_data: Datos de muestra (opcional)
        
        Returns:
            Relación verificada con explicación del LLM
        """
        prompt = self._create_verification_prompt(
            relationship, source_table_info, target_table_info, sample_data
        )
        
        # Llamar a Ollama
        response = self._call_ollama(prompt)
        
        # Parsear respuesta
        verified = self._parse_verification_response(response, relationship)
        
        return verified
    
    def _create_verification_prompt(self, 
                                  relationship: 'RelationshipCandidate',
                                  source_table_info: Dict,
                                  target_table_info: Dict,
                                  sample_data: Optional[Dict] = None) -> str:
        """Crea el prompt para verificación"""
        prompt = f"""Analiza si existe una relación de base de datos válida entre estas tablas y columnas:

RELACIÓN PROPUESTA:
- Tabla origen: {relationship.source_table}
- Columna origen: {relationship.source_column}
- Tabla destino: {relationship.target_table} 
- Columna destino: {relationship.target_column}

INFORMACIÓN DE TABLA ORIGEN ({relationship.source_table}):
Columnas: {json.dumps(source_table_info.get('columns', []), indent=2)}

INFORMACIÓN DE TABLA DESTINO ({relationship.target_table}):
Columnas: {json.dumps(target_table_info.get('columns', []), indent=2)}

"""

        if sample_data:
            prompt += f"""
DATOS DE MUESTRA:
{relationship.source_table}: {json.dumps(sample_data.get(relationship.source_table, []), indent=2)}
{relationship.target_table}: {json.dumps(sample_data.get(relationship.target_table, []), indent=2)}
"""

        prompt += """
Responde en formato JSON con la siguiente estructura:
{
  "is_valid": true/false,
  "confidence": 0.0-1.0,
  "relationship_type": "foreign_key" o "junction_table" o "none",
  "cardinality": "1:1" o "1:N" o "N:1" o "N:M",
  "explanation": "explicación detallada",
  "recommendation": "acción recomendada"
}

Considera:
1. ¿Los nombres de las columnas sugieren una relación?
2. ¿Los tipos de datos son compatibles?
3. ¿La cardinalidad tiene sentido para el dominio?
4. ¿Hay evidencia en los datos de muestra?
"""
        
        return prompt
    
    def _call_ollama(self, prompt: str) -> str:
        """Llama a Ollama API"""
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get('response', '{}')
            else:
                print(f"Error en Ollama: {response.status_code}")
                return '{}'
                
        except Exception as e:
            print(f"Error al llamar Ollama: {e}")
            return '{}'
    
    def _parse_verification_response(self, response: str, 
                                   original: 'RelationshipCandidate') -> VerifiedRelationship:
        """Parsea la respuesta del LLM"""
        try:
            data = json.loads(response)
        except:
            # Si no puede parsear JSON, crear respuesta por defecto
            data = {
                "is_valid": False,
                "confidence": 0.5,
                "relationship_type": "unknown",
                "cardinality": "1:N",
                "explanation": "No se pudo parsear la respuesta del LLM",
                "recommendation": "Revisar manualmente"
            }
        
        return VerifiedRelationship(
            source_table=original.source_table,
            source_column=original.source_column,
            target_table=original.target_table,
            target_column=original.target_column,
            confidence=original.confidence,
            llm_confidence=float(data.get('confidence', 0.5)),
            relationship_type=data.get('relationship_type', 'foreign_key'),
            cardinality=data.get('cardinality', '1:N'),
            explanation=data.get('explanation', ''),
            is_valid=data.get('is_valid', False)
        )
    
    def verify_batch(self, 
                    relationships: List['RelationshipCandidate'],
                    schema_info: Dict,
                    sample_data: Optional[Dict] = None,
                    max_verifications: int = 10) -> List[VerifiedRelationship]:
        """
        Verifica un lote de relaciones
        
        Args:
            relationships: Lista de candidatos a verificar
            schema_info: Información completa del esquema
            sample_data: Datos de muestra por tabla
            max_verifications: Máximo número de verificaciones (para limitar costos)
        
        Returns:
            Lista de relaciones verificadas
        """
        verified_relationships = []
        
        # Ordenar por confianza y tomar las top N
        sorted_relationships = sorted(relationships, 
                                    key=lambda x: x.confidence, 
                                    reverse=True)[:max_verifications]
        
        print(f"\n🔍 Verificando {len(sorted_relationships)} relaciones con LLM...")
        
        for i, rel in enumerate(sorted_relationships):
            print(f"  [{i+1}/{len(sorted_relationships)}] "
                  f"{rel.source_table}.{rel.source_column} → "
                  f"{rel.target_table}.{rel.target_column}")
            
            # Obtener información de las tablas
            source_info = schema_info.get(rel.source_table, {})
            target_info = schema_info.get(rel.target_table, {})
            
            # Verificar con LLM
            verified = self.verify_relationship(
                rel, source_info, target_info, sample_data
            )
            
            verified_relationships.append(verified)
            
            # Pequeña pausa para no sobrecargar
            time.sleep(0.5)
        
        return verified_relationships
    
    def generate_verification_report(self, 
                                   verified: List[VerifiedRelationship]) -> str:
        """Genera un reporte de las verificaciones"""
        report = []
        report.append("\n" + "="*80)
        report.append("REPORTE DE VERIFICACIÓN CON LLM")
        report.append("="*80)
        
        valid = [v for v in verified if v.is_valid]
        invalid = [v for v in verified if not v.is_valid]
        
        report.append(f"\n✅ Relaciones VÁLIDAS: {len(valid)}")
        report.append("="*40)
        
        for rel in valid:
            report.append(f"\n{rel.source_table}.{rel.source_column} → "
                         f"{rel.target_table}.{rel.target_column}")
            report.append(f"  Cardinalidad: {rel.cardinality}")
            report.append(f"  Confianza LLM: {rel.llm_confidence:.1%}")
            report.append(f"  Explicación: {rel.explanation[:100]}...")
        
        if invalid:
            report.append(f"\n\n❌ Relaciones NO VÁLIDAS: {len(invalid)}")
            report.append("="*40)
            
            for rel in invalid:
                report.append(f"\n{rel.source_table}.{rel.source_column} → "
                             f"{rel.target_table}.{rel.target_column}")
                report.append(f"  Razón: {rel.explanation[:100]}...")
        
        return "\n".join(report)

# Clase de utilidad para instalación fácil de Ollama
class OllamaInstaller:
    @staticmethod
    def get_installation_instructions():
        """Retorna instrucciones para instalar Ollama"""
        return """
🚀 INSTALACIÓN DE OLLAMA (LLM Local Gratuito)
============================================

1. INSTALAR OLLAMA:
   
   MacOS/Linux:
   curl -fsSL https://ollama.ai/install.sh | sh
   
   Windows:
   Descarga desde: https://ollama.ai/download

2. INICIAR SERVIDOR:
   ollama serve

3. INSTALAR UN MODELO (elige uno):
   
   Modelos recomendados:
   - ollama pull llama2      # 3.8GB, buena calidad
   - ollama pull mistral     # 4.1GB, muy buena calidad
   - ollama pull phi         # 1.6GB, más liviano
   - ollama pull codellama   # 3.8GB, optimizado para código

4. VERIFICAR INSTALACIÓN:
   curl http://localhost:11434/api/tags

¡Listo! Ya puedes usar LLMs locales gratuitamente.
"""

# Función alternativa sin LLM
def verify_without_llm(relationships: List['RelationshipCandidate']) -> List[VerifiedRelationship]:
    """
    Verificación básica sin LLM para cuando Ollama no está disponible
    """
    verified = []
    
    for rel in relationships:
        # Lógica simple basada en reglas
        is_valid = rel.confidence > 0.7
        cardinality = "1:N"  # Por defecto
        
        # Inferir cardinalidad por nombres
        if rel.source_column.endswith('_id') and rel.target_column == 'id':
            cardinality = "N:1"
        elif 'unique' in str(rel.evidence).lower():
            cardinality = "1:1"
        
        verified.append(VerifiedRelationship(
            source_table=rel.source_table,
            source_column=rel.source_column,
            target_table=rel.target_table,
            target_column=rel.target_column,
            confidence=rel.confidence,
            llm_confidence=rel.confidence,  # Usar misma confianza
            relationship_type=rel.relationship_type,
            cardinality=cardinality,
            explanation=f"Verificación basada en reglas: {', '.join(rel.evidence)}",
            is_valid=is_valid
        ))
    
    return verified