from typer.testing import CliRunner
from main import app

runner = CliRunner()
result = runner.invoke(app, ["status"])
print("STDOUT:", result.stdout)
