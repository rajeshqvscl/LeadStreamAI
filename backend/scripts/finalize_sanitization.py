import os
import re

scripts_dir = "scripts"
for filename in os.listdir(scripts_dir):
    if filename.endswith(".py"):
        filepath = os.path.join(scripts_dir, filename)
        with open(filepath, "r") as f:
            content = f.read()
        
        # Check if we need to add import os
        if "os.getenv" in content and "import os" not in content:
            content = "import os\n" + content
        
        # Ensure we also load dotenv if it's available, otherwise it won't work in local scripts
        if "os.getenv" in content and "load_dotenv" not in content:
            if "from dotenv import load_dotenv" not in content:
                # Add at the top after imports
                lines = content.split('\n')
                import_idx = 0
                for i, line in enumerate(lines):
                    if line.startswith("import ") or line.startswith("from "):
                        import_idx = i + 1
                lines.insert(import_idx, "from dotenv import load_dotenv")
                lines.insert(import_idx + 1, "load_dotenv()")
                content = '\n'.join(lines)
        
        with open(filepath, "w") as f:
            f.write(content)

print("Sanitization complete.")
