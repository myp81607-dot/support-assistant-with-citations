"""The same document contract is used by JSON import and the browser editor."""
from pydantic import BaseModel, Field, model_validator


class DocumentContent(BaseModel):
    text: str = Field(min_length=10, max_length=6000)
    fact_key: str = Field(default="", max_length=80, pattern=r"^[a-z0-9_]*$")
    fact_value: str = Field(default="", max_length=120)

    @model_validator(mode="after")
    def check_fact(self):
        self.text, self.fact_value = self.text.strip(), self.fact_value.strip()
        if len(self.text) < 10:
            raise ValueError("Document text is too short.")
        if bool(self.fact_key) != bool(self.fact_value):
            raise ValueError("Policy key and value must both be supplied or both empty.")
        if self.fact_value and self.fact_value.lower() not in self.text.lower():
            raise ValueError("The policy value must also appear in the document text.")
        return self


class Document(DocumentContent):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9][a-z0-9-]*$")
    title: str = Field(min_length=3, max_length=160)


class DocUpdate(DocumentContent):
    expected_version: int = Field(ge=1)
