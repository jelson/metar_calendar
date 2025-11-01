# Hourly METAR Predictor

### Installation

```bash
gem install jekyll bundler
bundle install
jekyll serve
```

Then view the site at `http://localhost:4000`

### TODO: Backend Integration

Replace the placeholder code in `handleSubmit()` function (line ~270 in app.js) with:

```javascript
// Example:
const response = await fetch(`/api/weather/${selectedAirport.icao}/${month}`);
const imageUrl = await response.json();
// Display the image
```
