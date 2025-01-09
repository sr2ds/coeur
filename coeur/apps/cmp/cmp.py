from coeur.apps.cmp.engine import Engine

import typer

app = typer.Typer()


@app.command(
    help="Generate a new blog post entry. Optional parameters: img_url (default: None), custom_prompt (default: None), custom_path (default: yyyy/mm/dd/{full-title-post}/), model (default: 'gpt-4o-mini')"
)
def title_to_post(
    title: str,
    img_url: str = None,
    custom_prompt: str = None,
    custom_path: str = None,
    model: str = "gpt-4o-mini",
) -> None:
    """
    Generate a new blog post entry using OpenAI API based on the provided title.\n
    This command uses the Engine to generate a complete blog post from the given title.\n
    You can optionally specify an image URL, a custom prompt to influence the tone or theme,\n
    and a custom path for defining the blog post URL.
    """
    Engine().title_to_post(
        title,
        model,
        img_url=img_url,
        custom_prompt=custom_prompt,
        custom_path=custom_path,
    )
