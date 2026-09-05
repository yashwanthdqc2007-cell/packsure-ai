# PackSure AI — Frontend

React + Vite + TypeScript + Tailwind CSS

## Pages

| Route | Page | Description |
|---|---|---|
| `/` | Dashboard | Overview, recent scans, stats |
| `/scan/new` | NewScan | Image upload and category selection |
| `/scan/:id/processing` | Processing | Real-time processing status |
| `/scan/:id/results` | Results | Compliance verdict and field breakdown |
| `/history` | History | Paginated scan history |
| `/scan/:id/report` | Report | Printable / exportable compliance report |

## TODO

- Implement page components
- Implement API integration via scanService
- Add loading states and error handling
- Add annotated evidence image viewer
