
## STACK ##
- Frontend: ReactJS, TypeScript strict
- Backend: Python 3.11+, FastAPI, AsyncIO
- Database: CockroachDB
- Styling: Tailwind only
- Dev: use uv and pyproject.toml, Makefile, ruff, black, basedPyRight
- Tests: use pyTest
- UI Tests: Use playright and puppeteer to do your own UI testing.

## HARD RULES ##
- Never install a new dependency without asking
- Never modify the database schema without showing a migration plan
- All API calls go through FastAPI
- Variables go in .env

## PATTERNS ##
- Always run unit tests after changes
- Strive for 75%+ code coverage
- Document designs in markdown files
