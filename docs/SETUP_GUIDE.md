# Advanced Setup & Technical Architecture

## Docker Deployment
### Using Docker Compose
```yaml
services:
  bot:
    build: .
    env_file: .env
    restart: always
```
Run with: `docker-compose up -d`

## Database Management
Eigen Bot uses **aiosqlite** for high-performance asynchronous operations.
- `botdata.db`: Main storage for tickets and CodeBuddy.
- `tags.db`: Dedicated tag storage.
- `starboard.db`: Starboard message mapping.

## Security
- **Environment Variables:** Sensitive tokens are never hardcoded.
- **Permission Checks:** Role-based access control (RBAC) ensures only authorized users can use Admin/Staff commands.
- **Sanitization:** All user inputs are sanitized to prevent SQL injection.

[← Back to README](../README.md)
