import { test, expect } from '@playwright/test'

test.describe('Login Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
  })

  test('should show login form', async ({ page }) => {
    await expect(page.locator('input[name="username"]')).toBeVisible()
    await expect(page.locator('input[name="password"]')).toBeVisible()
    await expect(page.locator('button[type="submit"]')).toBeVisible()
  })

  test('should show error for invalid credentials', async ({ page }) => {
    await page.fill('input[name="username"]', 'invalid')
    await page.fill('input[name="password"]', 'invalid')
    await page.click('button[type="submit"]')
    await expect(page.locator('text=Invalid username or password')).toBeVisible()
  })
})

test.describe('Dashboard', () => {
  test('should redirect to login when not authenticated', async ({ page }) => {
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login/)
  })
})

test.describe('Lead Pipeline', () => {
  test('should show lead list when authenticated', async ({ page }) => {
    // This would need proper auth setup
    // await page.goto('/dashboard/leads')
    // await expect(page.locator('text=Lead Pipeline')).toBeVisible()
    test.skip('Requires auth setup')
  })
})