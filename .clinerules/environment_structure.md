# Environment Structure

When creating or modifying environment configurations, follow this directory structure:

```
environments/
└── [environment_name]/
    ├── main.py            # Main deployment configuration
    ├── secrets/ 
    │   └── config_env.yaml    # Environment configuration
    └── .gitignore         # Ignore generated files
```

Always maintain this structure to ensure consistency across all environments.
