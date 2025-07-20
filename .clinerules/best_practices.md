# Best Practices

When working with this project, follow these best practices:

## Component Creation

- Specify dependencies explicitly with `depends_on`
- Create components in logical order (infrastructure → services)
- Keep sensitive information in secrets directory
- Use absolute imports for components
- When passing variables to `create_XXX_XXX` functions, pass directly from `XXX_config.get('key')`

## Code Organization

- Maintain consistent directory structure as specified in environment_structure.md
- Follow the main.py pattern as specified in main_py_pattern.md
- Use descriptive variable names that reflect their purpose
- Group related components together in the code

## Configuration Management

- Store all environment-specific configuration in `secrets/config_env.yaml`
- Use environment variables for sensitive information
- Follow the established pattern for loading and using configuration values
- Ensure all required configuration is documented in example files
