# PHONENDO 

- `author`: Jose Luis Parrilla Fuentes 
- `email`: jlpf0006@red.ujaen.es


# 1. Introducción 

Phonendo es una plataforma diseñada para manejar datos generados por dispositivos portatiles, basado en una arquitectura de basada en microservicios modular.

La propuesta inicial de phonendo definía una arquitectura distribuida compuesta por distintos servicios, los cuales incluyen los `Reader`, los `Manager`, los `Storage`, los `Verfier` y los `Publisher`. El proposito de esta arquitectura es capturar los datos de los dispositivos portatiles, verificar la integridad y la proveniencia de los datos, y la posterior publicación confiable en una infraestructura segura.

En esta nueva actualización, el `Reader` recive datos brutos de sensores locales o conectados por bluetooth, estandarizados mediante una ontología común.
Enviar las observaciones estructuradas al `Manager` usando comunicaciones basadas en HTTP. Este diseño permite a Phonendo soportar un amplio despliegue de sensores y escenarios. 

El objetivo final es contruir un robusto , extensible y fácilmenete desplegable sistema que pueda servir para futuras implementaciones de Phonendo. 


# 2. Objetivos

El objetivo principal de este proyecto es diseñar e implementar Phonendo de forma que seacapaz de correr en disposivitos portatiles mientras soporta una variedad de sensores y mecanismos de comunicación. 

Para lograr esta meta, he definido los siguientes objetivos concretos.

## 2.1. Construir un Reader compatible

Desarrollar un Reader ligero que pueda ser ejectutado y formar la entrada de los sensores. 

El reader debe de ser capaz de: 

- Obtener datos de los sensores conectados al dispositivo.
- Soportar sensores locales y conectador por bluetooth. 
- Manegar distintos dispositivos conectados al mismo Reader.
- Soportar dispositivos con multimples sensores. 
- Enviar información estandarizada al `Manager` a través de comunicaciones HTTP 


## 2.2. Definir una ontología común


Diseñar o adoptar una ontología común que provea una estandarización para representar la información relacionada de los sensores.


Esta ontología debe ser capaz de describir: 


- Dispositivos.
- Sensores.
- Observaciones en bruto.
- Unidades de medida.
- Marcas de tiempo.
- Método de adquisición del sensores.
- Lecturas periodicas .
- Lecturas por eventos.
- Proveniencia de los datos.


La ontología debería estar lo  más estandarizada posible para mejorar la interoperabilidad con modelos semánticos existentens y futuras extensiones de la plataforma.

## 2.3. Ind `phonendoSensors` library

Create a dedicated library, named `phonendoSensors`, responsible for acting as an abstraction layer between physical sensors and the Reader.

This library should provide a unified interface for interacting with different types of sensors, regardless of whether they are local sensors, Bluetooth devices, or future sensor integrations.

Its responsibilities include:

- Reading data from supported sensors.
- Normalizing raw sensor outputs.
- Applying sensor-specific configurations.
- Exposing a common interface to the Reader.
- Supporting both periodic and event-based sensors.


## 2.4. Proveer herramientas de despliegue y entorno


Construir las herramientas necesarias para simplicar el despligue de Phonendo tanto como sea posible. 

Esto incluye :

- Archivos de configuración.
- Scripts de Despliegue.
- Contenedores de cada servicios.
- Ejemplos y tutoriales.

## 2.5. Asegurar rosbustez y escabilidad

La plataforma debe de ser capaz de:

- Seguir operando aunque falle un servicio individual.
- Soportar multiples microservicios operando independientemente.
- Poder integrar una gran cantidad de sensore.
- Mantener los datos consistentes en todo el ciclo de datos. 


# 3. Arquitectura general

![hola](reader.png)

# 4. Ciclo de vida
    Un dato en bruto es recodigo por un sensor, el cual se encuentra en un dispositivo
    dicho dispositivo envía los datos en bruto al reader , el reader estandariza lo recibido y lo envía al manager.

    1. Matching / registro del dispositivo
    2. Recepción de datos
    3. Procesamiento de datos + Storage -> estado "Captured"
    4. Verification
    5. Storage -> estado "Verified"
    6. Publication
    7. Storage -> estado "Published" / fin del ciclo
    

    El manager registra los datos 
# 5. Ontology
    una ontología común que comunique 


# 6. Comunitation details 

# 7. Proyect 

# 8. Examples and tutorials

# 9. Desing decisions
    Un dispositivo es contiene una MAC y sensores 
    el disposiutivo es identificado por su MAC 
# 10. References 

La idea del reader es que vaya dentro del dispositivo portatil , 

El reader se ejecutará en dicho dispositivo y mediante http envería al manager los datos de los sensores recogidos

Se hace necesaria una ontología común universal para poder trabajar con todo tipo de sensores y que el reader lo entienda


Entonces la librería phonendoSensors Sería la encargada de posicionarse entre el los sensores y el reader 

El reader debe de tener disponibles configuraciones para todo tipo de sensores y también limitaciones por parte del manager

El reader debe gestionar :
        Sensores concretos: Sensores que se disparan en ciertos eventos concretos
        Sensores periodicos: Sensores que siempre están enviadno información 
            - intervalos de timepo , tiemouts etc etc

Todo esto debe ser configurable por el reader 

También phonendo debe ser reescrito en rust y entender dicha ontología 


La libería también debe de gestionar , sensores por bluetooth , y locales 



El texto dice que el Manager tiene entre sus responsabilidades certificar los datos y la procedencia; para eso, cada mensaje se firma con una clave asociada al wearable, generada usando la MAC del wearable y una contraseña del Manager mediante SHA256

.

Después, en la parte de Verifier, dice que el Verifier valida la integridad del dato usando heurísticas y genera como resultado un mensaje firmado que timestampa el dato capturado; por ejemplo, comprueba rangos permitidos y timestamps antiguos .


# Esquema  de schema.org

 La intención es tener un esquema que sirva de lenguaje común para la comunicación de todos los sensores 
https://schema.org/docs/iot-gettingstarted.html


Más enlaces sobre ontologías

La principal y recomendada:
https://www.w3.org/ns/sosa/ → SOSA (Sensor, Observation, Sample, and Actuator)
Esta es el núcleo ligero y más usado para describir cualquier tipo de sensor y sus observaciones.

Versión completa:
https://www.w3.org/ns/ssn/ → SSN (Semantic Sensor Network Ontology)

Documentación oficial:
https://www.w3.org/TR/vocab-ssn/ (especificación SSN)
https://www.w3.org/TR/vocab-ssn-2023/ (edición más reciente)


Estandart de sensores para proveer de significado a las anotaciones de los sensores:
 https://www.ogc.org/standards/om/

http://portal.opengeospatial.org/files/55939


Docunentación de owl: https://www.w3.org/2007/09/OWL-Overview-es.html


Protegé  software para crear ontologías: https://protege.stanford.edu/

RDF  para mierdas
https://www.w3.org/RDF/
https://www.seofreelance.es/que-es-rdf-introduccion-a-rdf/


https://rdflib.readthedocs.io/en/stable/

https://www.w3.org/TR/owl-time/#time:TemporalEntity

plyvel referencia para la base de datos: https://plyvel.readthedocs.io/en/latest/ 




Claro. Te dejo una anotación ordenada para documentación/notas.

Notas sobre tokens, firmas y confianza en Phonendo
1. Token del Reader

El token sirve para autorizar la comunicación HTTP entre el Reader y el Manager.

Por ejemplo:

{
  "token": "reader-api-token",
  "readerId": "reader-001",
  "deviceId": "device-001",
  "payload": "..."
}

Este token responde a la pregunta:

¿Este Reader/dispositivo está autorizado para enviar datos al Manager?

Pero no firma criptográficamente el dato. Es decir, el token no demuestra por sí solo que el contenido del payload no haya sido manipulado.

2. Firma del Manager

El artículo indica que el Manager tiene la responsabilidad de certificar datos y procedencia. Para ello, cada mensaje se firma con una clave asociada al wearable/device, generada usando la MAC address del dispositivo y una contraseña propia del Manager mediante SHA256.

Conceptualmente:

MAC del device + secreto del Manager
        ↓
SHA256 / derivación de clave
        ↓
clave o material criptográfico asociado al device
        ↓
firma del mensaje

La firma del Manager debería significar:

Este dato ha sido aceptado por un Manager concreto como procedente de un device registrado.

No significa que el dato sea médicamente correcto o válido. Solo certifica procedencia dentro del sistema Phonendo.

Para que sea útil, la firma no debe cubrir solo el deviceId, sino el evento completo o su hash:

eventId + deviceId + readerId + payloadHash + capturedAt

Así se evita que alguien reutilice una firma válida en otro payload distinto.

3. Firma del Verifier

El Verifier tiene otra función. No certifica simplemente que el device exista, sino que el dato ha sido validado.

El Verifier debería comprobar, por ejemplo:

- que el TTL/RDF es parseable
- que la observación es SOSA válida
- que el deviceId coincide
- que el sensor pertenece al dispositivo
- que el datatype es correcto
- que la unidad es correcta
- que el valor está dentro de rango
- que el timestamp no es antiguo ni futuro

Si todo está bien, firma el resultado:

payloadHash + managerSignature + verificationResult + verifierSignedAt

La firma del Verifier significa:

Este dato concreto ha pasado las reglas de verificación de este Verifier.

4. Diferencia entre token, firma del Manager y firma del Verifier
Token:
    Autoriza la llamada HTTP.

Manager signature:
    Certifica procedencia.
    “Este dato viene de este device registrado y ha sido aceptado por este Manager.”

Verifier signature:
    Certifica validación.
    “Este dato ha sido comprobado y pasa las reglas del Verifier.”
5. Claves públicas/privadas

Si se quiere que otros servicios puedan verificar firmas sin compartir secretos, lo correcto es usar criptografía asimétrica:

private key -> firma
public key  -> verifica

Por ejemplo:

Manager private key:
    firma procedencia.

Manager public key:
    permite al Verifier, Publisher o auditor comprobar esa firma.

Verifier private key:
    firma validación.

Verifier public key:
    permite al Publisher o consumidor comprobar que el dato fue verificado.

Si se usa HMAC/SHA256 con un secreto compartido, entonces quien quiera verificar necesita conocer el secreto. Eso puede ser menos adecuado si se quiere separar responsabilidades entre Manager y Verifier.

6. Varios Managers, Verifiers y Publishers

Phonendo puede tener múltiples instancias de cada servicio:

Reader(s)
Manager(s)
Storage(s)
Verifier(s)
Publisher(s)

Por eso cada firma debe incluir identidad del servicio:

{
  "managerId": "manager-uja-001",
  "managerKeyId": "manager-uja-key-001",
  "managerSignature": "...",

  "verifierId": "verifier-uja-health-001",
  "verifierKeyId": "verifier-uja-health-key-001",
  "verifierSignature": "...",

  "publisherId": "publisher-iota-001"
}

Así, quien lea el dato publicado puede decidir:

- si confía en ese Manager
- si confía en ese Verifier
- si la clave pública sigue siendo válida
- si la firma corresponde realmente al payload publicado
7. Flujo recomendado
1. Reader envía dato al Manager:
   token + readerId + deviceId + payload

2. Manager:
   valida token
   comprueba que el device está registrado
   calcula payloadHash
   firma procedencia
   guarda evento como Captured

3. Verifier:
   recibe el evento firmado por Manager
   valida el contenido
   firma el resultado de la verificación
   devuelve Verified o Rejected

4. Publisher:
   publica solo eventos Verified
   idealmente publica también firmas, ids de claves y payloadHash

5. Consumidor/auditor:
   verifica firmas y decide en qué entidades confía
8. Idea clave

La firma del Manager y la firma del Verifier no tienen el mismo significado:

Manager:
    confianza en la procedencia.

Verifier:
    confianza en la validez del dato.

Un dato publicado debería poder responder a estas preguntas:

¿Quién lo capturó?
¿De qué device viene?
¿Qué Manager aceptó su procedencia?
¿Qué Verifier lo validó?
¿Qué payload exacto fue firmado?
¿Con qué claves se firmó?
¿Puedo verificar esas firmas?


DOCUMENTACION DE BLUETOOTH 

Bluetooth Serie , claísco SPP RFCOMM 

BLE Bluetooth Low energy 


SINO SE PUEDE OBTENER LA MAC DE UN SENSOR BLUETOOTH LA POLITICA ES ASIGNAR LA MAC DEL READER


Vale , Aquí tengo una dictomía , 


# Problemática De Identificación Y Semántica En Sensores Bluetooth

Durante la integración de sensores Bluetooth en Phonendo aparece una limitación importante: no siempre es posible obtener de forma automática toda la información necesaria para registrar un dispositivo y construir observaciones semánticas completas.

En transports como RFCOMM, el Reader recibe principalmente un flujo de bytes desde un puerto serie virtual, por ejemplo /dev/rfcomm0. Ese flujo puede contener mediciones, pero no garantiza por sí mismo información como la MAC real del dispositivo remoto, el tipo de dispositivo, el identificador del sensor, la propiedad observada, el procedimiento de medición o la entidad observada.

Esto genera un problema porque Phonendo necesita asociar cada dato recibido a un origen concreto y representarlo mediante una ontología común. Sin esa información, el Reader no puede saber de forma fiable si un valor como 36.7 representa temperatura corporal, temperatura ambiente, batería, humedad u otra magnitud.

Existen dos enfoques principales:

Que el sensor envíe toda la información necesaria junto con cada medición o durante un handshake inicial.
Que el Reader disponga de una configuración donde se describan los dispositivos, sensores y propiedades esperadas.
El primer enfoque permite construir un Reader más universal, ya que el propio sensor informa de su identidad y semántica. Sin embargo, exige que cada sensor o microcontrolador implemente un protocolo más complejo.

El segundo enfoque permite usar sensores más simples, que solo envían valores o mensajes mínimos, pero desplaza la responsabilidad al Reader, que debe estar configurado previamente para interpretar esos datos correctamente.

Por este motivo, Phonendo adopta un enfoque híbrido: siempre que el mensaje recibido incluya metadatos, el Reader los utilizará; cuando falten, intentará completarlos mediante configuración local; y si tampoco existe configuración suficiente, aplicará políticas de fallback controladas, como generar identificadores pseudónimos estables.

En el caso de la MAC, si no se puede obtener la dirección física del dispositivo Bluetooth remoto, el Reader puede generar una MAC local administrada y pseudónima, por ejemplo con prefijo 02, derivada de información estable como el identificador del Reader y la fuente local del dato. Esto evita inventar una MAC de fabricante y permite mantener una identidad estable dentro del sistema.

La política general de resolución de identidad y semántica será:Bien , entonces tendríamos que establer una política en el reader , 1 , atender a configuración 2 atender a sensores completos (si así se configura en el despliegue del reader ) , 3 atender datos raros que no entren dentro del conjunto 1  ni dentro del conjunto 2 , estos se pondrá , "raw" "unknow" , y de esto