# Web de Phonendo

React 19 + Vite. Cuatro páginas independientes, sin enlaces entre los paneles:

| Página | Entrada | Contenido |
| --- | --- | --- |
| `index.html` | `src/pages/home.jsx` | Portada: consola y casos de uso |
| `operator.html` | `src/pages/operator.jsx` | Consola del operador: lienzo, logs, Docker y contratos |
| `patient.html` | `src/pages/patient.jsx` | Pagos recibidos por una cuenta Stellar |
| `insurer.html` | `src/pages/insurer.jsx` | Pagos realizados por el contrato |

## Uso

Requiere Node.js 20 o superior.

```sh
npm install
npm run build      # páginas estáticas en dist/
npm test           # lógica del lienzo (node --test) y componentes (Vitest + jsdom)
npm run dev        # desarrollo con recarga; /api/local va a tools/web.sh (WEB_PORT, 8080)
```

`./tools/web.sh` compila la web y sirve `dist/` junto a la API local del operador.
El inspector usa formularios React Visual/JSON sincronizados. Reader aplica en
directo; los otros contenedores gestionados reinician al guardar. Los borradores
permanecen en memoria al cambiar de nodo; servicios externos solo generan archivos.

## Providers y consumers

El estado compartido vive en providers de contexto (`src/providers`). Cada uno
expone su estado y sus acciones, y los componentes los consumen con su hook:

| Provider | Hook | Qué publica |
| --- | --- | --- |
| `I18nProvider` | `useI18n` | Idioma, `t(clave)` y `opText(es, en)`. Se guarda en el navegador |
| `ToastProvider` | `useToast` | `toast(mensaje)` y el aviso flotante |
| `PaymentsProvider` | `usePayments` | Pagos `session_paid` del RPC, estado de la red y pagos nuevos |
| `NetworkProvider` | `useNetwork` | Servicios del despliegue, su estado y el nodo seleccionado |
| `OperatorProvider` | `useOperator` | Puente con `/api/local`: sondeo cada 3 s, logs, Readers, contenedores y acciones |
| `DeployDialogProvider` | `useDeployDialog` | Diálogo para desplegar un contenedor |

Cada página compone solo los providers que necesita. Los paneles de paciente y
aseguradora usan `I18n`, `Toast` y `Payments`; la consola añade `Network`,
`Operator` y `DeployDialog`.

## Estructura

- `src/views` y `src/components`: componentes. `canvas/` es el lienzo libre y
  `operator/` el inspector, los logs y el diálogo.
- `src/lib`: funciones sin React (formato, pagos de Stellar, archivos de configuración).
- `service_network/`: lógica pura del lienzo (modelos, estado, layout, geometría y
  cliente de `/api/local`), probada con `node --test`. Ver su [README](service_network/README.md).
- `styles.css`, `home.css` y `service_network/styles.css`: estilos de todas las páginas.
