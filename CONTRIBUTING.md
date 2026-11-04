# Contributing to OpenPark

Thank you for your interest in contributing to **OpenPark**, an open-source, real-time parking platform for metro cities!

## Code of Conduct
We are committed to providing a welcoming, inclusive, and harassment-free environment for everyone. Please be respectful and constructive in all discussions and pull requests.

## How Can You Contribute?
- **Good First Issues**:
  - Add bounding-box presets for additional metro cities (Mumbai, Delhi, Chennai, Hyderabad).
  - Add dark mode support to the driver map interface (`app/index.html`).
  - Implement PWA service worker with offline tile caching and Web Push notifications.
  - Extend the edge sensor module with OpenCV license-plate or vehicle contour detection.
  - Add unit tests for crowdsourced spam filtering rules.
- **Reporting Bugs**:
  - Open an issue describing the expected vs actual behavior, your OS, and browser.
- **Submitting Pull Requests**:
  1. Fork the repository and create your feature branch: `git checkout -b feature/amazing-feature`.
  2. Follow existing code formatting and linting.
  3. Ensure all automated tests pass:
     ```bash
     cd backend && pytest test_api.py -v
     ```
  4. Submit your pull request with a descriptive title and summary of changes.

## Data Attribution & Privacy
- **OpenStreetMap Data**: OpenStreetMap data is licensed under the Open Data Commons Open Database License (ODbL). Always attribute `© OpenStreetMap contributors` in user interfaces and documentation.
- **Driver Privacy**: OpenPark is designed privacy-first. Live GPS coordinates are strictly ephemeral: never persist driver location history to databases.

## License
By contributing to OpenPark, you agree that your contributions will be licensed under the Apache-2.0 License.
