package main

import (
	"image/color"

	"fyne.io/fyne/v2"
	"fyne.io/fyne/v2/theme"
)

// customTheme extends the default dark theme with JetBrains Mono font
type customTheme struct{}

// Font returns the JetBrains Mono font for text styles
func (t *customTheme) Font(style fyne.TextStyle) fyne.Resource {
	return resourceJetBrainsMonoNLRegularTtf
}

// Color returns theme colors (using default dark theme colors)
func (t *customTheme) Color(name fyne.ThemeColorName, variant fyne.ThemeVariant) color.Color {
	return theme.DefaultTheme().Color(name, variant)
}

// Icon returns theme icons (using default theme icons)
func (t *customTheme) Icon(name fyne.ThemeIconName) fyne.Resource {
	return theme.DefaultTheme().Icon(name)
}

// Size returns theme sizes (using default theme sizes)
func (t *customTheme) Size(name fyne.ThemeSizeName) float32 {
	return theme.DefaultTheme().Size(name)
}
