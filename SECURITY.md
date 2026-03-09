# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in OpenInsure, please report it responsibly:

1. **Do NOT** open a public GitHub issue
2. **Email** security concerns to the maintainers
3. **Include** a description of the vulnerability, steps to reproduce, and potential impact

We will acknowledge receipt within 48 hours and provide a detailed response within 7 days.

## Security Practices

OpenInsure follows these security practices:

### Authentication & Authorization
- Microsoft Entra ID for all authentication
- Managed Identity for Azure service connections (no keys/passwords)
- Role-based access control (RBAC) with least privilege
- Agent identity: each AI agent operates under its own managed identity

### Data Protection
- Encryption at rest (Azure service defaults)
- Encryption in transit (TLS 1.2+)
- Azure Key Vault for secret management
- No credentials in source code or environment files committed to Git

### AI Security
- Microsoft Defender for AI threat protection
- Prompt injection detection
- Data exfiltration prevention
- Adversarial input validation
- Decision record immutability (tamper-proof audit trail)

### Compliance
- EU AI Act conformity (high-risk system requirements)
- GDPR data protection
- SOC 2 Type II alignment
- Regular security scanning (bandit, GitHub Advanced Security)

### CI/CD Security
- Dependency scanning
- Secret scanning
- Code scanning (CodeQL where applicable)
- Signed commits recommended
