from coeur.apps.cmp.engine import Engine

import typer

app = typer.Typer()


@app.command()
def title_to_post(title: str, img_url: str = None, custom_prompt: str = None) -> None:
    """Generate a new blog post entry using OpenAI API based on the provided title.\n
    This command leverages the Engine to create a full post using the specified title.\n
    Optionally, you can include an image URL to enhance the post's visual appeal and
    a custom prompt to tailor the content according to specific themes or tones.
    """
    Engine().title_to_post(title, img_url, custom_prompt)
