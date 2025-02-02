import vertexai
from vertexai.generative_models import GenerativeModel

# TODO(developer): Update project_id
# PROJECT_ID = "your-project-id"
vertexai.init(project="code-institute-433215", location="us-central1")

model = GenerativeModel("gemini-1.5-flash-001")

response = model.generate_content(
    "What is a mortgage?"
)

print(response.text)
