// theme-toggle.js

document.addEventListener('DOMContentLoaded', () => {
  const themeToggleButton = document.getElementById('theme-toggle-btn');
  const body = document.body;

  // Function to apply the theme and update the button text
  const applyTheme = (theme) => {
    const isLight = theme === 'light';
    body.classList.toggle('light-mode', isLight);
    themeToggleButton.textContent = isLight ? 'Switch to Dark Mode' : 'Switch to Light Mode';
  };

  // Event listener for the toggle button
  themeToggleButton.addEventListener('click', () => {
    const isLightMode = body.classList.contains('light-mode');
    const newTheme = isLightMode ? 'dark' : 'light';
    // Save the new theme to localStorage
    localStorage.setItem('theme', newTheme);
    applyTheme(newTheme);
  });

  // Check for a saved theme in localStorage on page load
  // Default to 'dark' if no theme is saved
  const savedTheme = localStorage.getItem('theme') || 'dark';
  applyTheme(savedTheme);
});
