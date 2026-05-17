# Contributing to Shamsi Smart

Thank you for your interest in contributing! This document outlines how to contribute effectively.

---

## Ways to Contribute

- **Bug reports** — Open an issue with reproduction steps
- **Equipment data** — Add new panel/inverter models with specs and Egyptian market prices
- **Climate data** — Add more Egyptian governorate coverage to ESED
- **Translations** — Improve the Arabic UI or add other language support
- **Optimiser improvements** — Propose new objective functions or constraint handling
- **Tests** — Increase coverage, especially for edge cases
- **Documentation** — Improve or translate documentation

---

## Development Setup

```bash
git clone https://github.com/shamsi-smart/ai-engine.git
cd ai-engine
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # pytest, coverage, black, flake8
python manage.py migrate
python manage.py test
```

---

## Code Standards

- **Style:** PEP 8, enforced by `black` (line length 100)
- **Type hints:** All new functions must include type annotations
- **Docstrings:** Google-style docstrings for all public functions
- **Tests:** New features must include tests; target ≥80% coverage
- **Commits:** Conventional commits format (`feat:`, `fix:`, `docs:`, `test:`)

```bash
# Format code
black ai_engine/ api/ scripts/ tests/

# Lint
flake8 ai_engine/ api/ --max-line-length=100

# Run tests
python -m pytest tests/ -v

# Run with coverage
python -m pytest tests/ --cov=ai_engine --cov-report=html
```

---

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature-name`
3. Write code and tests
4. Ensure all tests pass: `python -m pytest tests/ -v`
5. Update documentation if needed
6. Submit PR with a clear description of what and why

### PR Checklist

- [ ] Tests pass locally (`python -m pytest tests/ -v`)
- [ ] Code formatted with `black`
- [ ] Type hints added for new functions
- [ ] Docstrings written
- [ ] `CHANGELOG.md` updated (if applicable)
- [ ] Related issue linked in PR description

---

## Adding Equipment Data

To add a new solar panel or inverter:

1. Add to `api/fixtures/equipment.json` or via Django admin
2. Update `ai_engine/export/pvsyst_exporter.py` with PVsyst format specs (if PAN/OND export needed)
3. Add a test in `tests/test_exports.py`

**Required panel fields:** model name, manufacturer, Wp, efficiency, Voc, Isc, Vmpp, Impp, temp coefficient (Pmax), NOCT, dimensions, weight, price (EGP), warranty.

**Required inverter fields:** model name, manufacturer, rated kW, efficiency, Euro-efficiency, MPPT count, MPPT voltage range, Voc max, Isc max, price (EGP).

---

## Reporting Issues

Please include:
- Python version and OS
- Exact error message and traceback
- Minimal reproduction steps
- Expected vs actual behaviour

Use the issue template: `.github/ISSUE_TEMPLATE/bug_report.md`

---

## Code of Conduct

We follow the [Contributor Covenant](https://www.contributor-covenant.org/) v2.1. Be respectful, inclusive, and constructive. Issues or PRs exhibiting harassment will be closed.

---

## Licence

By contributing, you agree that your contributions will be licensed under the MIT Licence.
