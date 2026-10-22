# Publishing

Never commit tokens or put them into command-line arguments. Revoke any token pasted into
a conversation. Release only after CI passes and the built wheel has been installed/tested.

Preferred: configure a **pending Trusted Publisher** in your PyPI account:

- PyPI project: `phonipy`
- GitHub owner: `udanish50`
- Repository: `PhoniPy`
- Workflow filename: `publish.yml`
- Environment: `pypi`

After all tests pass, publishing a GitHub release tagged `v0.2.0` triggers the workflow.
It repeats the tests, builds and checks artifacts, verifies the tag, and uses GitHub OIDC
to publish without a long-lived token. Configuring that publisher requires the PyPI owner's
authenticated account; the workflow alone cannot register it.

Alternative: store a fresh PyPI token through Twine's keyring integration or enter it at
Twine's interactive password prompt. Use username `__token__`. Do not paste it into chat.
Before uploading, run `python -m twine check dist/*`, then `python -m twine upload dist/*`.
The API-token display label is arbitrary: the actual package name is `phonipy`, not `phonepy`.

Successful build or GitHub push does not imply successful PyPI publication. Verify the
PyPI project and a fresh `pip install phonipy==0.2.0` after upload.
