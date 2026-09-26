"""Authentication workflow for the dashboard."""

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from selectors import EMAIL_INPUT, LOGIN_BUTTON, LOGIN_ERROR, PASSWORD_INPUT


def login(page: Page, base_url: str, email: str, password: str) -> None:
    """Log in and wait until the application leaves its login page."""
    page.goto(base_url, wait_until="domcontentloaded")
    page.locator(EMAIL_INPUT).first.fill(email)
    page.locator(PASSWORD_INPUT).first.fill(password)
    page.locator(LOGIN_BUTTON).first.click()

    page.wait_for_load_state("domcontentloaded")

    password_input = page.locator(PASSWORD_INPUT).first
    try:
        password_input.wait_for(state="hidden", timeout=10_000)
        return
    except PlaywrightTimeoutError:
        pass

    error = page.locator(LOGIN_ERROR).first
    if error.is_visible():
        message = error.text_content() or "Login failed"
        raise RuntimeError(message.strip())

    raise RuntimeError("Login did not complete; verify the credentials and selectors")
