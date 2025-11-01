// Airport Search Autocomplete
(function() {
    'use strict';

    // State
    let airports = [];
    let fuse = null;
    let selectedAirport = null;
    let currentFocusIndex = -1;
    let currentResults = [];

    // DOM Elements
    const searchInput = document.getElementById('airportSearch');
    const dropdown = document.getElementById('autocompleteDropdown');
    const monthSelect = document.getElementById('monthSelect');
    const searchForm = document.getElementById('searchForm');
    const loadingState = document.getElementById('loadingState');
    const resultDisplay = document.getElementById('resultDisplay');
    const resultTitle = document.getElementById('resultTitle');
    const errorState = document.getElementById('errorState');
    const errorMessage = document.getElementById('errorMessage');
    const prevMonthBtn = document.getElementById('prevMonthBtn');
    const nextMonthBtn = document.getElementById('nextMonthBtn');
    const mobileMonthNav = document.getElementById('mobileMonthNav');
    const prevMonthBtnMobile = document.getElementById('prevMonthBtnMobile');
    const nextMonthBtnMobile = document.getElementById('nextMonthBtnMobile');

    // Initialize
    async function init() {
        try {
            // Load airport data
            const response = await fetch('/assets/data/airports.json');
            if (!response.ok) throw new Error('Failed to load airport data');
            airports = await response.json();

            // Initialize Fuse.js with custom options
            fuse = new Fuse(airports, {
                keys: [
                    { name: 'icao', weight: 0.3 },
                    { name: 'iata', weight: 0.3 },
                    { name: 'name', weight: 0.2 },
                    { name: 'city', weight: 0.2 }
                ],
                threshold: 0.4,
                includeScore: true,
                minMatchCharLength: 1,
                ignoreLocation: true
            });

            setupEventListeners();
            setDefaultMonth();

            // Check for URL hash and load if present
            if (window.location.hash) {
                loadFromHash();
            } else {
                searchInput.focus();
            }
        } catch (error) {
            console.error('Initialization error:', error);
            showError('Failed to load airport database. Please refresh the page.');
        }
    }

    // Set default month to current month
    function setDefaultMonth() {
        const currentMonth = new Date().getMonth() + 1;
        monthSelect.value = currentMonth;
    }

    // Load airport/month from URL hash (#KSMO/6)
    function loadFromHash() {
        const hash = window.location.hash.slice(1); // Remove #
        const parts = hash.split('/');

        if (parts.length !== 2) return;

        const airportCode = parts[0].toUpperCase();
        const month = parseInt(parts[1]);

        if (!month || month < 1 || month > 12) return;

        // Find airport by ICAO or IATA code
        const airport = airports.find(a =>
            a.icao === airportCode || a.iata === airportCode
        );

        if (!airport) return;

        // Set month and airport
        monthSelect.value = month;
        selectedAirport = airport;
        const displayText = `${airport.icao || airport.iata} - ${airport.name}`;
        searchInput.value = displayText;

        // Show mobile month navigation
        mobileMonthNav.classList.remove('hidden');

        // Trigger search
        searchForm.requestSubmit();
    }

    // Update URL hash when search is performed
    function updateHash(airportCode, month) {
        window.location.hash = `${airportCode}/${month}`;
    }

    // Setup event listeners
    function setupEventListeners() {
        // Search input
        searchInput.addEventListener('input', handleInput);
        searchInput.addEventListener('click', (e) => {
            e.target.value = '';
            selectedAirport = null;
            hideDropdown();
        });
        searchInput.addEventListener('blur', handleBlur);
        searchInput.addEventListener('keydown', handleKeyDown);

        // Form submission
        searchForm.addEventListener('submit', handleSubmit);

        // Month navigation buttons (desktop)
        prevMonthBtn.addEventListener('click', () => changeMonth(-1));
        nextMonthBtn.addEventListener('click', () => changeMonth(1));

        // Month navigation buttons (mobile)
        prevMonthBtnMobile.addEventListener('click', () => changeMonth(-1));
        nextMonthBtnMobile.addEventListener('click', () => changeMonth(1));

        // Click outside to close dropdown
        document.addEventListener('click', (e) => {
            if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
                hideDropdown();
            }
        });
    }

    // Change month (direction: -1 for previous, 1 for next)
    function changeMonth(direction) {
        if (!selectedAirport) return;

        let newMonth = parseInt(monthSelect.value) + direction;

        // Wrap around
        if (newMonth < 1) {
            newMonth = 12;
        } else if (newMonth > 12) {
            newMonth = 1;
        }

        monthSelect.value = newMonth;
        searchForm.requestSubmit();
    }

    // Handle input changes
    function handleInput(e) {
        const query = e.target.value.trim();

        if (query.length === 0) {
            hideDropdown();
            return;
        }

        performSearch(query);
    }

    // Perform search with custom scoring
    function performSearch(query) {
        if (!fuse) return;

        // Get fuzzy search results
        let results = fuse.search(query);

        // Custom scoring for exact and substring matches
        const queryUpper = query.toUpperCase();

        results = results.map(result => {
            const airport = result.item;
            let customScore = result.score;

            // Exact code match (highest priority)
            if (airport.icao === queryUpper || airport.iata === queryUpper) {
                customScore = 0;
            }
            // Code starts with query
            else if (airport.icao?.startsWith(queryUpper) || airport.iata?.startsWith(queryUpper)) {
                customScore = 0.1;
            }
            // Substring match in codes
            else if (airport.icao?.includes(queryUpper) || airport.iata?.includes(queryUpper)) {
                customScore = 0.2;
            }
            // Name starts with query (case insensitive)
            else if (airport.name?.toLowerCase().startsWith(query.toLowerCase())) {
                customScore = 0.25;
            }
            // Substring match in name
            else if (airport.name?.toLowerCase().includes(query.toLowerCase())) {
                customScore = 0.3;
            }
            // City starts with query
            else if (airport.city?.toLowerCase().startsWith(query.toLowerCase())) {
                customScore = 0.35;
            }

            return {
                ...result,
                customScore
            };
        });

        // Sort by custom score
        results.sort((a, b) => a.customScore - b.customScore);

        // Limit to top 10 results
        currentResults = results.slice(0, 10);

        displayResults(currentResults);
    }

    // Display search results
    function displayResults(results) {
        if (results.length === 0) {
            hideDropdown();
            return;
        }

        dropdown.innerHTML = '';
        currentFocusIndex = -1;

        results.forEach((result, index) => {
            const airport = result.item;
            const item = createResultItem(airport, index);
            dropdown.appendChild(item);
        });

        showDropdown();

        // Set first item as focused
        if (results.length > 0) {
            setFocusedItem(0);
        }
    }

    // Create result item element
    function createResultItem(airport, index) {
        const div = document.createElement('div');
        div.className = 'autocomplete-item px-4 py-3 cursor-pointer border-b border-gray-100 last:border-b-0 transition';
        div.dataset.index = index;

        const codes = [airport.iata, airport.icao].filter(Boolean).join(' / ');

        // Format location: "City, Country" or just "Country" if no city
        const location = airport.city
            ? `${escapeHtml(airport.city)}, ${escapeHtml(airport.country)}`
            : escapeHtml(airport.country);

        div.innerHTML = `
            <div class="flex justify-between items-center gap-4">
                <div class="min-w-0 flex-1">
                    <div class="font-semibold text-gray-800">${escapeHtml(airport.name)}</div>
                    <div class="text-sm text-gray-600">${location}</div>
                </div>
                <div class="text-sm font-mono text-blue-600 flex-shrink-0 whitespace-nowrap">${escapeHtml(codes)}</div>
            </div>
        `;

        // Click handler
        div.addEventListener('mousedown', (e) => {
            e.preventDefault(); // Prevent blur event
            selectAirport(airport);
        });

        // Hover handler
        div.addEventListener('mouseenter', () => {
            setFocusedItem(index);
        });

        return div;
    }

    // Handle keyboard navigation
    function handleKeyDown(e) {
        const items = dropdown.querySelectorAll('.autocomplete-item');

        if (items.length === 0) return;

        switch(e.key) {
            case 'ArrowDown':
                e.preventDefault();
                currentFocusIndex = Math.min(currentFocusIndex + 1, items.length - 1);
                setFocusedItem(currentFocusIndex);
                break;

            case 'ArrowUp':
                e.preventDefault();
                currentFocusIndex = Math.max(currentFocusIndex - 1, 0);
                setFocusedItem(currentFocusIndex);
                break;

            case 'Enter':
                e.preventDefault();
                if (currentFocusIndex >= 0 && currentResults[currentFocusIndex]) {
                    selectAirport(currentResults[currentFocusIndex].item);
                    searchForm.requestSubmit();
                } else if (currentResults.length > 0) {
                    // If no item is focused but there are results, select the first one
                    selectAirport(currentResults[0].item);
                    searchForm.requestSubmit();
                }
                break;

            case 'Escape':
                hideDropdown();
                searchInput.blur();
                break;
        }
    }

    // Set focused item in dropdown
    function setFocusedItem(index) {
        const items = dropdown.querySelectorAll('.autocomplete-item');
        items.forEach(item => item.classList.remove('selected'));

        if (items[index]) {
            items[index].classList.add('selected');
            items[index].scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }

        currentFocusIndex = index;
    }

    // Select an airport
    function selectAirport(airport) {
        selectedAirport = airport;

        // Update input with ICAO code (preferred) or IATA
        const displayText = `${airport.icao || airport.iata} - ${airport.name}`;
        searchInput.value = displayText;

        hideDropdown();

        // Show mobile month navigation
        mobileMonthNav.classList.remove('hidden');

        // Auto-submit the form
        searchForm.requestSubmit();
    }

    // Handle blur event
    function handleBlur() {
        // Delay to allow click events to fire
        setTimeout(() => {
            hideDropdown();
        }, 200);
    }

    // Show/hide dropdown
    function showDropdown() {
        dropdown.classList.remove('hidden');
    }

    function hideDropdown() {
        dropdown.classList.add('hidden');
        currentFocusIndex = -1;
    }

    // Handle form submission
    async function handleSubmit(e) {
        e.preventDefault();

        if (!selectedAirport) {
            showError('Please select an airport from the list');
            return;
        }

        const month = monthSelect.value;
        const monthNames = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                           'July', 'August', 'September', 'October', 'November', 'December'];

        // Update URL hash for shareability
        const airportCode = selectedAirport.icao || selectedAirport.iata;
        updateHash(airportCode, month);

        // Show loading state
        hideError();
        resultDisplay.classList.add('hidden');
        loadingState.classList.remove('hidden');

        // Blur search input to prevent mobile keyboard from appearing when touching chart
        searchInput.blur();

        try {
            // Call the API using the 'query' field (which contains the correct identifier for IEM)
            const airportCode = selectedAirport.query || selectedAirport.icao || selectedAirport.iata;
            const url = `${API_BASE_URL}statistics?airport_code=${encodeURIComponent(airportCode)}&month=${month}`;

            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`API returned ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            if (data.error) {
                throw new Error(data.error);
            }

            // Hide loading state
            loadingState.classList.add('hidden');

            // Update result title with airport code (ICAO preferred, or IATA)
            const displayCode = selectedAirport.icao || selectedAirport.iata;
            resultTitle.textContent = `${monthNames[month]} at ${displayCode} (${selectedAirport.name})`;

            // Show result display first
            resultDisplay.classList.remove('hidden');

            // Scroll to results
            resultDisplay.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

            // Display the chart after container is visible and sized
            setTimeout(() => {
                displayWeatherChart(data, selectedAirport, monthNames[month]);
            }, 0);
        } catch (error) {
            loadingState.classList.add('hidden');
            console.error('API error:', error);
            showError(`Failed to load weather data: ${error.message}`);
        }
    }

    // Display weather data as interactive Plotly chart
    function displayWeatherChart(data, airport, monthName) {
        const resultImage = document.getElementById('resultImage');
        resultImage.innerHTML = '<div id="plotlyChart" style="width: 100%; height: 100%;"></div>';

        // Extract hours and data for each flight condition
        const hours = [];
        const vfrData = [];
        const mvfrData = [];
        const ifrData = [];
        const lifrData = [];
        let missingHours = 0;

        for (let hour = 0; hour < 24; hour++) {
            hours.push(hour);
            const stats = data.hourly_stats[hour];
            if (stats) {
                vfrData.push(stats.VFR);
                mvfrData.push(stats.MVFR);
                ifrData.push(stats.IFR);
                lifrData.push(stats.LIFR);
            } else {
                vfrData.push(0);
                mvfrData.push(0);
                ifrData.push(0);
                lifrData.push(0);
                missingHours++;
            }
        }

        // Show warning if there are missing hours
        const warningElement = document.getElementById('partialCoverageWarning');
        if (missingHours > 0) {
            warningElement.classList.remove('hidden');
        } else {
            warningElement.classList.add('hidden');
        }

        // Create traces for each flight condition (VFR first for bottom stacking)
        const traces = [
            {
                x: hours,
                y: vfrData,
                name: 'VFR',
                type: 'bar',
                marker: { color: 'green' },
                hovertemplate: 'Hour %{x}:00<br>VFR: %{y:.1%}<extra></extra>'
            },
            {
                x: hours,
                y: mvfrData,
                name: 'MVFR',
                type: 'bar',
                marker: { color: 'blue' },
                hovertemplate: 'Hour %{x}:00<br>MVFR: %{y:.1%}<extra></extra>'
            },
            {
                x: hours,
                y: ifrData,
                name: 'IFR',
                type: 'bar',
                marker: { color: 'red' },
                hovertemplate: 'Hour %{x}:00<br>IFR: %{y:.1%}<extra></extra>'
            },
            {
                x: hours,
                y: lifrData,
                name: 'LIFR',
                type: 'bar',
                marker: { color: 'magenta' },
                hovertemplate: 'Hour %{x}:00<br>LIFR: %{y:.1%}<extra></extra>'
            }
        ];

        // Detect mobile viewport
        const isMobile = window.innerWidth < 768;

        // Layout configuration
        const layout = {
            barmode: 'stack',
            height: isMobile ? 300 : 400,
            xaxis: {
                title: {
                    text: 'UTC hour',
                    standoff: 10
                },
                dtick: 1,
                range: [-0.5, 23.5],
                fixedrange: true
            },
            yaxis: {
                title: isMobile ? '' : {
                    text: 'Fraction of Days',
                    standoff: 10
                },
                tickformat: '.0%',
                fixedrange: true
            },
            legend: {
                traceorder: 'reversed',
                orientation: 'h',
                x: 0.5,
                xanchor: 'center',
                y: 1.02,
                yanchor: 'bottom'
            },
            hovermode: 'closest',
            margin: { l: isMobile ? 40 : 70, r: isMobile ? 5 : 10, t: 40, b: 70 }
        };

        // Render the chart with full width
        Plotly.newPlot('plotlyChart', traces, layout, {
            responsive: true,
            displayModeBar: false
        });
    }

    // Show error message
    function showError(message) {
        errorMessage.textContent = message;
        errorState.classList.remove('hidden');
        setTimeout(() => {
            errorState.classList.add('hidden');
        }, 5000);
    }

    // Hide error message
    function hideError() {
        errorState.classList.add('hidden');
    }

    // Utility: Escape HTML
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Initialize on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
