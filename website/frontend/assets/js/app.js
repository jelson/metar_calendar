// Airport Search Autocomplete
(function() {
    'use strict';

    // State
    let airports = [];
    let fuse = null;
    let selectedAirport = null;
    let currentFocusIndex = -1;
    let currentResults = [];

    const MONTH_NAMES = ['', 'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'];
    const MONTH_ABBRS = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
        'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

    // DOM Elements
    const searchInput = document.getElementById('airportSearch');
    const dropdown = document.getElementById('autocompleteDropdown');
    // Single combined control: "year" selects the year-round view, "1".."12"
    // selects a month in the hourly view
    const timeframeSelect = document.getElementById('timeframeSelect');
    const searchCard = document.getElementById('searchCard');
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
            const response = await fetch('/assets/data/airports_v4.json');
            if (!response.ok) throw new Error('Failed to load airport data');
            airports = await response.json();

            // Add a cleaned location field with parenthesized text removed,
            // e.g. "Paris (Roissy-en-France, Val-d'Oise), IDF, FR" -> "Paris, IDF, FR"
            airports.forEach(a => {
                a.locationClean = a.location?.replace(/\s*\([^)]*\)/g, '') || '';
            });

            // Initialize Fuse.js for fuzzy matching only (exact/substring
            // matching is handled separately in performSearch)
            fuse = new Fuse(airports, {
                keys: [
                    { name: 'codes', weight: 0.4 },
                    { name: 'name', weight: 0.3 },
                    { name: 'location', weight: 0.3 }
                ],
                threshold: 0.4,
                includeScore: true,
                minMatchCharLength: 1,
                ignoreLocation: true
            });

            setupEventListeners();
            setDefaultTimeframe();
            syncTimeframeUI();

            // Hide loading state and show search card now that we're ready
            loadingState.classList.add('hidden');
            searchCard.classList.remove('hidden');

            // Check for URL hash and load if present
            if (window.location.hash) {
                loadFromHash();
            } else {
                searchInput.focus();
            }
        } catch (error) {
            console.error('Initialization error:', error);
            loadingState.classList.add('hidden');
            searchCard.classList.remove('hidden');
            showError('Failed to load airport database. Please refresh the page.');
        }
    }

    // Set default timeframe to the current calendar month
    function setDefaultTimeframe() {
        const currentMonth = new Date().getMonth() + 1;
        timeframeSelect.value = String(currentMonth);
    }

    // Load airport/timeframe from URL hash (#KSMO/6, or #KSMO/year for the
    // year-round view)
    function loadFromHash() {
        const hash = window.location.hash.slice(1); // Remove #
        const parts = hash.split('/');

        if (parts.length !== 2) return;

        const airportCode = parts[0].toUpperCase();
        const timeframePart = parts[1].toLowerCase();

        if (timeframePart === 'year') {
            timeframeSelect.value = 'year';
        } else {
            const month = parseInt(timeframePart);
            if (!month || month < 1 || month > 12) return;
            timeframeSelect.value = String(month);
        }
        // Sync right away, not after the airport lookup: the timeframe sticks
        // even if the airport isn't found
        syncTimeframeUI();

        // Find airport by display code
        const airport = airports.find(a => a.display === airportCode);

        if (!airport) return;

        // Select the airport (triggers the search)
        selectAirport(airport);
    }

    // Update URL hash when search is performed
    function updateHash(display, monthOrYear) {
        history.replaceState(null, '', `#${display}/${monthOrYear}`);
    }

    // Whether the year-round view is selected (rather than a single month).
    // Always read from the timeframe select itself, so the view can never
    // disagree with what the dropdown shows.
    function isYearlyView() {
        return timeframeSelect.value === 'year';
    }

    // Sync the month-navigation UI to the timeframe select's current value.
    // Hides the arrow buttons and mobile nav in yearly mode, since neither
    // applies when there's no single month selected.
    function syncTimeframeUI() {
        const isYearly = isYearlyView();

        // Inline styles (rather than Tailwind classes) unconditionally
        // override the responsive "hidden md:flex" classes on the month nav
        // buttons, which a class toggle alone can't reliably beat.
        // visibility (not display) keeps them reserving their layout space
        // -- removing them from the flex row entirely would widen the chart
        // card next to them and leave already-rendered Plotly charts sized
        // for the old, narrower width.
        prevMonthBtn.style.visibility = isYearly ? 'hidden' : '';
        nextMonthBtn.style.visibility = isYearly ? 'hidden' : '';
        if (isYearly) {
            mobileMonthNav.classList.add('hidden');
        } else if (selectedAirport) {
            mobileMonthNav.classList.remove('hidden');
        }
    }

    // Clear search input and reset state
    function clearSearchInput() {
        searchInput.value = '';
        selectedAirport = null;
        hideDropdown();
        searchInput.focus();
    }

    function setupEventListeners() {
        // Search input
        searchInput.addEventListener('input', handleInput);
        searchInput.addEventListener('click', clearSearchInput);
        searchInput.addEventListener('blur', handleBlur);
        searchInput.addEventListener('keydown', handleKeyDown);

        // Form submission
        searchForm.addEventListener('submit', handleSubmit);

        // Changing the timeframe (a month, or Year-Round) re-runs the search
        // if an airport is already selected (programmatic changes don't fire
        // 'change', so the prev/next buttons won't double-submit)
        timeframeSelect.addEventListener('change', () => {
            syncTimeframeUI();
            if (selectedAirport) {
                searchForm.requestSubmit();
            }
        });

        // Month navigation buttons (desktop)
        prevMonthBtn.addEventListener('click', () => changeMonth(-1));
        nextMonthBtn.addEventListener('click', () => changeMonth(1));

        // Month navigation buttons (mobile)
        prevMonthBtnMobile.addEventListener('click', () => changeMonth(-1));
        nextMonthBtnMobile.addEventListener('click', () => changeMonth(1));

        // Temperature unit toggle (°C / °F)
        document.getElementById('tempUnitToggle').addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-unit]');
            if (btn) {
                setTempUnit(btn.dataset.unit);
            }
        });

        // Click outside to close dropdown
        document.addEventListener('click', (e) => {
            if (!searchInput.contains(e.target) && !dropdown.contains(e.target)) {
                hideDropdown();
            }
        });

        // Global keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Slash key to clear and focus search input
            if (e.key === '/' && document.activeElement !== searchInput) {
                e.preventDefault();
                clearSearchInput();
            }

            // Left/Right arrow keys to navigate months (only when not in an input field)
            if ((e.key === 'ArrowLeft' || e.key === 'ArrowRight') &&
                document.activeElement !== searchInput &&
                document.activeElement.tagName !== 'SELECT') {

                if (e.key === 'ArrowLeft') {
                    e.preventDefault();
                    changeMonth(-1);
                } else if (e.key === 'ArrowRight') {
                    e.preventDefault();
                    changeMonth(1);
                }
            }
        });
    }

    // Change month (direction: -1 for previous, 1 for next)
    function changeMonth(direction) {
        if (!selectedAirport || isYearlyView()) return;

        let newMonth = parseInt(timeframeSelect.value) + direction;

        // Wrap around
        if (newMonth < 1) {
            newMonth = 12;
        } else if (newMonth > 12) {
            newMonth = 1;
        }

        timeframeSelect.value = String(newMonth);
        searchForm.dispatchEvent(new Event('submit', { cancelable: true }));
    }

    // Handle input changes
    function handleInput(e) {
        const query = e.target.value.trim();

        // Reset focus index whenever user types
        currentFocusIndex = -1;

        if (query.length === 0) {
            hideDropdown();
            return;
        }

        performSearch(query);
    }

    // Check if query appears as a whole word in text
    function hasWholeWord(text, query) {
        const re = new RegExp('\\b' + query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'i');
        return re.test(text);
    }

    // Score an airport against the query. Lower score = better match.
    function scoreAirport(airport, queryLower, queryUpper) {
        const hasExactCode = airport.codes?.some(code => code === queryUpper);
        const hasStartingCode = airport.codes?.some(code => code.startsWith(queryUpper));
        const hasSubstringCode = airport.codes?.some(code => code.includes(queryUpper));

        // Code matches (highest priority)
        if (hasExactCode) return 0;
        if (hasStartingCode) return 0.1;
        if (hasSubstringCode) return 0.2;

        // Whole-word matches
        const nameWord = airport.name && hasWholeWord(airport.name, queryLower);
        const locWord = airport.locationClean && hasWholeWord(airport.locationClean, queryLower);

        if (nameWord && airport.name.toLowerCase().startsWith(queryLower)) return 0.25;
        if (locWord && airport.locationClean.toLowerCase().startsWith(queryLower)) return 0.3;
        if (nameWord) return 0.35;
        if (locWord) return 0.4;

        // Substring matches (e.g. "paris" inside "parish")
        if (airport.name?.toLowerCase().includes(queryLower)) return 0.5;
        if (airport.locationClean?.toLowerCase().includes(queryLower)) return 0.55;
        if (airport.location?.toLowerCase().includes(queryLower)) return 0.6;

        return null;
    }

    // Perform search with custom scoring
    function performSearch(query) {
        if (!fuse) return;

        const queryLower = query.toLowerCase();
        const queryUpper = query.toUpperCase();

        // Direct substring search to guarantee exact matches aren't missed
        const seen = new Set();
        const results = [];

        airports.forEach(airport => {
            const score = scoreAirport(airport, queryLower, queryUpper);
            if (score !== null) {
                seen.add(airport.query);
                results.push({ item: airport, customScore: score });
            }
        });

        // Supplement with Fuse.js fuzzy results
        fuse.search(query).forEach(result => {
            if (!seen.has(result.item.query)) {
                seen.add(result.item.query);
                results.push({ item: result.item, customScore: 0.7 + result.score });
            }
        });

        // Sort by custom score, then by airport size (large=0, medium=1, small=2)
        results.sort((a, b) =>
            a.customScore - b.customScore ||
            (a.item.size ?? 3) - (b.item.size ?? 3)
        );

        // Limit to top 20 results
        currentResults = results.slice(0, 20);

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

        const codes = airport.codes ? airport.codes.join(' / ') : '';
        const location = airport.location ? escapeHtml(airport.location) : '';

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
                } else if (currentResults.length > 0) {
                    // If no item is focused but there are results, select the first one
                    selectAirport(currentResults[0].item);
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

        // Update input with display code and airport name
        const displayText = `${airport.display} - ${airport.name}`;
        searchInput.value = displayText;

        hideDropdown();

        // Show mobile month navigation (hourly view only)
        if (!isYearlyView()) {
            mobileMonthNav.classList.remove('hidden');
        }

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

        const month = timeframeSelect.value;
        const isYearly = isYearlyView();

        // Update URL hash for shareability
        updateHash(selectedAirport.display, isYearly ? 'year' : month);

        // Show loading state
        hideError();
        const isReload = !resultDisplay.classList.contains('hidden');
        if (isReload) {
            // Hide content but preserve layout space to prevent page reflow
            resultDisplay.style.minHeight = resultDisplay.offsetHeight + 'px';
            resultDisplay.style.position = 'relative';
            resultDisplay.style.visibility = 'hidden';

            // Overlay a visible spinner inside the invisible container
            const spinner = document.createElement('div');
            spinner.id = 'reloadSpinner';
            // The overlay spans the whole (possibly taller-than-viewport)
            // hidden result area; the sticky inner box keeps the spinner
            // pinned inside the visible part of the screen
            spinner.style.cssText = 'visibility:visible; position:absolute; inset:0;';
            spinner.innerHTML = '<div style="position:sticky; top:35vh; display:flex; flex-direction:column; align-items:center;"><div class="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div><p class="mt-4 text-gray-600">Loading...</p></div>';
            resultDisplay.appendChild(spinner);
        } else {
            loadingState.classList.remove('hidden');
        }

        // Blur search input to prevent mobile keyboard from appearing when touching chart
        searchInput.blur();

        try {
            // Call the API using the 'query' field (which contains the correct identifier for IEM)
            const url = isYearly
                ? `${API_BASE_URL}monthly_statistics?airport_code=${encodeURIComponent(selectedAirport.query)}`
                : `${API_BASE_URL}statistics?airport_code=${encodeURIComponent(selectedAirport.query)}&month=${month}`;

            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`API returned ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();

            if (data.error) {
                throw new Error(data.error);
            }

            // Update result title with display code
            resultTitle.textContent = isYearly
                ? `Year-round at ${selectedAirport.display} (${selectedAirport.name})`
                : `${MONTH_NAMES[month]} at ${selectedAirport.display} (${selectedAirport.name})`;

            loadingState.classList.add('hidden');
            resultDisplay.classList.remove('hidden');

            // Clean up reload overlay
            const spinner = document.getElementById('reloadSpinner');
            if (spinner) spinner.remove();
            resultDisplay.style.visibility = '';
            resultDisplay.style.minHeight = '';
            resultDisplay.style.position = '';

            const renderCharts = () => {
                const axis = buildAxis(data, isYearly);
                displayConditionsChart(data, axis);
                displayWindCharts(data, axis);
                displayTemperatureSection(data, axis);
                displayPrecipitationSection(data, axis);
            };

            if (isReload) {
                renderCharts();
            } else {
                // First load: render after container is visible and sized
                requestAnimationFrame(() => {
                    renderCharts();
                    requestAnimationFrame(() => {
                        resultDisplay.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                    });
                });
            }
        } catch (error) {
            loadingState.classList.add('hidden');
            const errSpinner = document.getElementById('reloadSpinner');
            if (errSpinner) errSpinner.remove();
            resultDisplay.style.visibility = '';
            resultDisplay.style.minHeight = '';
            resultDisplay.style.position = '';
            console.error('API error:', error);
            showError(`Failed to load weather data: ${error.message}`);
        }
    }

    // Convert a UTC hour + offset to compact AM/PM format
    // e.g., formatLocalHour(0, -7) => "5p", formatLocalHour(13, 5.5) => "6:30p"
    function formatLocalHour(utcHour, offsetHours) {
        let localHour = (utcHour + offsetHours) % 24;
        if (localHour < 0) localHour += 24;

        const hourInt = Math.floor(localHour);
        const minutes = Math.round((localHour - hourInt) * 60);

        const period = hourInt >= 12 ? 'p' : 'a';
        const displayHour = hourInt === 0 ? 12 : hourInt > 12 ? hourInt - 12 : hourInt;

        if (minutes > 0) {
            return `${displayHour}:${String(minutes).padStart(2, '0')}${period}`;
        }
        return `${displayHour}${period}`;
    }

    // The offset used to order the x axis by local time: the one in effect
    // mid-month (from the backend), or null when the timezone is unknown
    function getPrimaryOffset(data) {
        if (data.primary_utc_offset_hours !== undefined &&
            data.primary_utc_offset_hours !== null) {
            return data.primary_utc_offset_hours;
        }
        const utcOffsets = data.utc_offsets || [];
        return utcOffsets.length > 0 ? utcOffsets[0].utc_offset_hours : null;
    }

    // Map each UTC hour to its x position on the chart. With a known timezone
    // the axis runs 0-23 in local time, so UTC hour u sits at (u + offset) % 24;
    // otherwise the axis is plain UTC. Sorted by x so line traces draw cleanly.
    function buildHourMapping(data) {
        const offset = getPrimaryOffset(data);
        const mapping = [];
        for (let utc = 0; utc < 24; utc++) {
            const x = offset === null ? utc : (((utc + offset) % 24) + 24) % 24;
            mapping.push({ utc, x });
        }
        mapping.sort((a, b) => a.x - b.x);
        return mapping;
    }

    // Convert UTC sunrise/sunset to the axis timezone
    function localizeDaylight(daylightUtc, offset) {
        if (!daylightUtc || offset === null) return daylightUtc;
        const conv = h => (((h + offset) % 24) + 24) % 24;
        return {
            sunrise: conv(daylightUtc.sunrise),
            sunset: conv(daylightUtc.sunset),
        };
    }

    // Build per-hour hover labels: "14:00 UTC (2p PDT)" or "14:00 UTC" if no timezone
    function buildHourLabels(utcOffsets) {
        const labels = [];
        for (let h = 0; h < 24; h++) {
            let label = `${h}:00 UTC`;
            if (utcOffsets.length > 0) {
                const localParts = utcOffsets.map(o =>
                    `${formatLocalHour(h, o.utc_offset_hours)} ${o.abbr}`
                );
                label += ` (${localParts.join(' / ')})`;
            }
            labels.push(label);
        }
        return labels;
    }

    // Apply multi-line x-axis tick labels with local time rows to a chart
    // layout. The mapping determines where each UTC hour sits on the axis
    // (ordered by local time when the timezone is known).
    function applyTimezoneTicks(xaxis, utcOffsets, isMobile, mapping) {
        if (utcOffsets.length === 0) return;

        const tickvals = [];
        const ticktext = [];

        for (const { utc, x } of mapping) {
            tickvals.push(x);
            const lines = [`${utc}`];
            for (const offset of utcOffsets) {
                lines.push(formatLocalHour(utc, offset.utc_offset_hours));
            }
            ticktext.push(lines.join('<br>'));
        }

        // Label column on the left, perfectly aligned with data rows
        const labelLines = ['<b>UTC</b>'];
        for (const offset of utcOffsets) {
            labelLines.push(`<b>${offset.abbr}</b>`);
        }
        tickvals.unshift(-1);
        ticktext.unshift(labelLines.join('<br>'));

        xaxis.tickvals = tickvals;
        xaxis.ticktext = ticktext;
        xaxis.tickfont = { size: isMobile ? 8 : 10 };
        xaxis.tickangle = 0;
        xaxis.range = [-1.5, Math.max(...tickvals) + 0.5];
    }

    // Yellow daylight background shapes (handles daylight wrapping midnight UTC)
    function buildDaylightShapes(daylightUtc) {
        if (!daylightUtc) return [];

        const { sunrise, sunset } = daylightUtc;
        const shapeStyle = {
            type: 'rect',
            xref: 'x',
            yref: 'paper',
            y0: 0,
            y1: 1,
            fillcolor: 'rgba(255, 255, 0, 0.4)',
            line: { width: 0 },
            layer: 'below',
        };

        if (sunrise < sunset) {
            // Daylight doesn't wrap around midnight UTC (e.g., European airports)
            return [{ ...shapeStyle, x0: sunrise, x1: sunset }];
        }
        // Daylight wraps around midnight UTC (e.g., American airports)
        return [
            { ...shapeStyle, x0: -0.5, x1: sunset },
            { ...shapeStyle, x0: sunrise, x1: 23.5 },
        ];
    }

    // ---- Chart axis: everything that differs between the hourly view (one
    // month, x = hour of day, in local time when the timezone is known) and
    // the year-round view (x = calendar month, all hours of the day pooled).
    // Every chart function takes an axis and looks up each column's stats by
    // axis.keys (UTC hour or month number, matching the API's keys).
    function buildAxis(data, isYearly) {
        const isMobile = window.innerWidth < 768;

        if (isYearly) {
            return {
                isMobile,
                keys: MONTH_NAMES.slice(1).map((_, i) => i + 1),
                x: MONTH_ABBRS.slice(1),
                hoverLabels: MONTH_NAMES.slice(1),
                conditions: data.monthly_stats,
                // Every hour of every day in the month is one sample
                sampleUnit: 'Hours',
                periodPhrase: 'in each month, pooling all hours of the day',
                periodNoun: 'month',
                missingDataNoun: 'monthly',
                bottomMargin: 40,
                daylightShapes: [],
                xaxis: () => ({ zeroline: false, fixedrange: true }),
            };
        }

        const utcOffsets = data.utc_offsets || [];
        const hasTimezone = utcOffsets.length > 0;
        const mapping = buildHourMapping(data);
        const hourLabels = buildHourLabels(utcOffsets);
        // Base for tick labels, plus extra per timezone row (no x-axis title
        // when timezone rows are shown)
        const extraRowHeight = isMobile ? 12 : 16;

        return {
            isMobile,
            keys: mapping.map(m => m.utc),
            x: mapping.map(m => m.x),
            hoverLabels: mapping.map(m => hourLabels[m.utc]),
            conditions: data.hourly_stats,
            // One sample per day at a fixed hour
            sampleUnit: 'Days',
            periodPhrase: 'at each hour',
            periodNoun: 'hour',
            missingDataNoun: 'hourly',
            bottomMargin: hasTimezone ? 25 + utcOffsets.length * extraRowHeight : 70,
            daylightShapes: buildDaylightShapes(
                localizeDaylight(data.daylight_utc, getPrimaryOffset(data))),
            xaxis: () => {
                const xaxis = {
                    title: hasTimezone ? '' : { text: 'UTC hour', standoff: 10 },
                    dtick: 1,
                    zeroline: false,
                    range: [-0.5, 23.5],
                    fixedrange: true
                };
                // Multi-line x-axis tick labels with local time rows
                applyTimezoneTicks(xaxis, utcOffsets, isMobile, mapping);
                return xaxis;
            },
        };
    }

    const LEGEND_ABOVE = {
        orientation: 'h',
        x: 0.5,
        xanchor: 'center',
        y: 1.02,
        yanchor: 'bottom'
    };

    // Layout shared by every chart; options override the chart-specific parts
    function chartLayout(axis, {
        height, mobileHeight, yTitle, yaxis = {}, top = 10, legend = LEGEND_ABOVE, ...extra
    }) {
        const isMobile = axis.isMobile;
        return {
            height: isMobile ? mobileHeight : height,
            xaxis: axis.xaxis(),
            yaxis: {
                title: isMobile ? '' : { text: yTitle, standoff: 10 },
                fixedrange: true,
                ...yaxis
            },
            legend,
            hovermode: 'closest',
            margin: { l: isMobile ? 40 : 70, r: isMobile ? 5 : 10, t: top, b: axis.bottomMargin },
            ...extra
        };
    }

    function plotChart(elementId, traces, layout) {
        return Plotly.newPlot(elementId, traces, layout, {
            responsive: true,
            displayModeBar: false
        });
    }

    // Per-column hover label rows, for use as a trace's customdata
    function hoverCustomdata(axis) {
        return axis.hoverLabels.map(label => [label]);
    }

    const CONDITION_COLORS = { VFR: 'green', MVFR: 'blue', IFR: 'red', LIFR: 'magenta' };

    // Stacked bars of flight condition fractions per column
    function displayConditionsChart(data, axis) {
        const resultImage = document.getElementById('resultImage');

        // Lock container height to prevent page reflow during content swap
        resultImage.style.minHeight = resultImage.offsetHeight + 'px';
        resultImage.innerHTML = '<div id="plotlyChart" style="width: 100%; height: 100%;"></div>';

        const stats = axis.keys.map(k => axis.conditions[k]);
        const missingColumns = stats.filter(s => !s).length;

        const warningElement = document.getElementById('partialCoverageWarning');
        if (missingColumns > 0) {
            document.getElementById('partialCoverageText').textContent =
                `ⓘ This airport has missing ${axis.missingDataNoun} data. ` +
                'Some airports only publish weather data when staffed by observers.';
        }
        warningElement.classList.toggle('hidden', missingColumns === 0);

        // VFR first for bottom stacking
        const customdata = hoverCustomdata(axis);
        const traces = Object.entries(CONDITION_COLORS).map(([cond, color]) => ({
            x: axis.x,
            y: stats.map(s => s ? s[cond] : 0),
            customdata,
            name: cond,
            type: 'bar',
            marker: { color },
            hovertemplate: `%{customdata[0]}<br>${cond}: %{y:.1%}<extra></extra>`
        }));

        const layout = chartLayout(axis, {
            height: 400,
            mobileHeight: 300,
            yTitle: `Fraction of ${axis.sampleUnit}`,
            yaxis: { tickformat: '.0%' },
            top: 40,
            legend: { ...LEGEND_ABOVE, traceorder: 'reversed' },
            barmode: 'stack',
            shapes: axis.daylightShapes,
        });

        plotChart('plotlyChart', traces, layout).then(() => {
            resultImage.style.minHeight = '';
        });
    }

    // Sequential ramp for wind speed bins (light = light air, dark = strong wind)
    const WIND_SPEED_COLORS = {
        '0-3 kt': '#e5e7eb',
        '4-8 kt': '#a7dbd4',
        '9-13 kt': '#6cc0b7',
        '14-18 kt': '#3d9d96',
        '>18 kt': '#0b4f4c',
    };

    // Show a chart section only when the API returned its stats (it returns
    // null when the airport has no such data, e.g. precipitation amounts
    // outside the US). Returns whether the section is shown.
    function showSection(sectionId, stats) {
        document.getElementById(sectionId).classList.toggle('hidden', !stats);
        return Boolean(stats);
    }

    // Display the two wind charts (speed distribution + direction heatmap)
    function displayWindCharts(data, axis) {
        const wind = data.wind;
        if (!showSection('windSection', wind)) return;

        document.getElementById('windDirCaption').textContent =
            `How often the wind blows from each direction (${wind.direction_step}° bins) ` +
            `${axis.periodPhrase}. Light winds (≤ ${wind.direction_min_kt} kt), calm and ` +
            'variable winds are not shown.';

        displayWindSpeedChart(wind, axis);
        displayWindDirectionChart(wind, axis);
    }

    // Stacked bars of wind speed bins per column, gust details in hover
    function displayWindSpeedChart(wind, axis) {
        // customdata rows: [column label, gust description]
        const customdata = [];
        const gustFreqs = [];
        axis.keys.forEach((key, i) => {
            const gust = wind.gust[key];
            gustFreqs.push(gust ? gust.freq : null);
            let gustText = 'Gusts: none recorded';
            if (gust && gust.freq > 0) {
                gustText = `Gusts in ${(gust.freq * 100).toFixed(0)}% of hours` +
                    ` (median ${Math.round(gust.median)} kt,` +
                    ` max ${Math.round(gust.max)} kt)`;
            }
            customdata.push([axis.hoverLabels[i], gustText]);
        });

        const traces = wind.speed_bins.map(bin => ({
            x: axis.x,
            y: axis.keys.map(k => wind.speed[k] ? wind.speed[k][bin] : 0),
            customdata,
            name: bin,
            type: 'bar',
            marker: { color: WIND_SPEED_COLORS[bin] },
            hovertemplate: `%{customdata[0]}<br>${bin}: %{y:.1%}<extra></extra>`
        }));

        // Overlay the fraction of hours with gusts as a line (same 0-100% axis)
        traces.push({
            x: axis.x,
            y: gustFreqs,
            customdata,
            name: 'Gusts (% of hours)',
            type: 'scatter',
            mode: 'lines+markers',
            line: { color: '#c2410c', width: 2 },
            marker: { size: 6 },
            hovertemplate: '%{customdata[0]}<br>%{customdata[1]}<extra></extra>'
        });

        plotChart('windSpeedChart', traces, chartLayout(axis, {
            height: 340,
            mobileHeight: 260,
            yTitle: `Fraction of ${axis.sampleUnit}`,
            yaxis: { tickformat: '.0%' },
            barmode: 'stack',
        }));
    }

    // Heatmap of wind direction frequency: x = column, y = direction in
    // degrees (20° bins), color = fraction of observations from that direction
    function displayWindDirectionChart(wind, axis) {
        const step = wind.direction_step;
        const numSectors = 360 / step;

        // Sector labels "000", "020", ... "340"
        const sectorLabels = Array.from({ length: numSectors },
            (_, s) => String(s * step).padStart(3, '0'));

        // Sector labels are bin centers; hovers show the full range so
        // "000" is unambiguous (it covers 350°-010°)
        const half = step / 2;
        const rangeLabels = sectorLabels.map((_, s) => {
            const from = String((s * step - half + 360) % 360).padStart(3, '0');
            const to = String((s * step + half) % 360).padStart(3, '0');
            return `${from}°–${to}°`;
        });

        // z[sector][column]; null (gap) for columns without data
        const z = sectorLabels.map((_, s) =>
            axis.keys.map(k => wind.direction[k] ? wind.direction[k][s] : null));
        const customdata = sectorLabels.map((_, s) =>
            axis.hoverLabels.map(label => [label, rangeLabels[s]]));

        const traces = [{
            type: 'heatmap',
            x: axis.x,
            y: sectorLabels,
            z,
            customdata,
            colorscale: [[0, '#ffffff'], [1, '#0f766e']],
            zmin: 0,
            xgap: 1,
            ygap: 1,
            hoverongaps: false,
            showscale: false,
            hovertemplate: '%{customdata[0]}<br>From %{customdata[1]}: %{z:.1%}<extra></extra>'
        }];

        plotChart('windDirChart', traces, chartLayout(axis, {
            height: 330,
            mobileHeight: 260,
            yTitle: 'Wind direction (°)',
            yaxis: {
                type: 'category',
                tickvals: sectorLabels.filter((_, s) => s % 3 === 0),
                tickfont: { size: axis.isMobile ? 8 : 10 },
            },
            // White instead of plotly's default gray, so columns without any
            // data (transparent gap columns) don't show up as gray bars
            plot_bgcolor: '#ffffff',
        }));
    }

    // Temperature unit toggle: persisted in localStorage, defaults to Celsius
    let tempUnit = localStorage.getItem('metarTempUnit') === 'F' ? 'F' : 'C';
    // The temperature chart currently displayed, kept together with the axis
    // it was drawn on so a unit change redraws it exactly as it was
    let displayedTemperature = null;

    function setTempUnit(unit) {
        tempUnit = unit;
        localStorage.setItem('metarTempUnit', unit);

        const toggle = document.getElementById('tempUnitToggle');
        toggle.querySelectorAll('button').forEach(btn => {
            const active = btn.dataset.unit === unit;
            btn.classList.toggle('bg-blue-600', active);
            btn.classList.toggle('text-white', active);
            btn.classList.toggle('text-gray-600', !active);
        });

        if (displayedTemperature) {
            displayTemperatureChart(displayedTemperature.temperature, displayedTemperature.axis);
        }
    }

    // Display the temperature/dewpoint chart in the current unit
    function displayTemperatureSection(data, axis) {
        displayedTemperature = null;
        if (!showSection('temperatureSection', data.temperature)) return;

        document.getElementById('temperatureCaption').textContent =
            `Shaded bands show the typical range (10th–90th percentile) ${axis.periodPhrase}; ` +
            'lines show the median.';

        displayedTemperature = { temperature: data.temperature, axis };
        setTempUnit(tempUnit);
    }

    // Display the precipitation chart
    function displayPrecipitationSection(data, axis) {
        if (!showSection('precipitationSection', data.precipitation)) return;

        document.getElementById('precipitationCaption').textContent =
            `How often measurable precipitation was reported ${axis.periodPhrase}, ` +
            'broken down by type.';

        displayPrecipitationChart(data.precipitation, axis);
    }

    // Temperature and dewpoint as median lines with a 10th-90th percentile
    // shaded band (a single average would hide day-to-day spread)
    function displayTemperatureChart(temperature, axis) {
        const stats = axis.keys.map(k => temperature.periods[k] || null);
        const customdata = hoverCustomdata(axis);

        // API values are Fahrenheit; convert to Celsius here if that's the
        // active display unit (percentiles are order-preserving under this
        // linear conversion, so no need to recompute from raw data). null
        // (missing dewpoint) must pass through unchanged -- "null - 32"
        // coerces to -32 in JS, which would otherwise plot a fake value.
        const toDisplay = tempUnit === 'C'
            ? f => f === null ? null : (f - 32) * 5 / 9
            : f => f;
        const unitLabel = tempUnit === 'C' ? '°C' : '°F';

        // Build a shaded percentile band + median line for one series
        // (temp or dewpoint). Two invisible traces (upper, lower-with-fill)
        // draw the band; showlegend is false on both so only the median
        // line's legend entry appears.
        function bandTraces(key, name, lineColor, bandColor) {
            const series = suffix => stats.map(s => s ? toDisplay(s[`${key}_${suffix}`]) : null);
            return [
                {
                    x: axis.x, y: series('p90'), mode: 'lines',
                    line: { width: 0 }, showlegend: false, hoverinfo: 'skip'
                },
                {
                    x: axis.x, y: series('p10'), mode: 'lines',
                    line: { width: 0 }, fill: 'tonexty', fillcolor: bandColor,
                    showlegend: false, hoverinfo: 'skip'
                },
                {
                    x: axis.x, y: series('median'), customdata, name,
                    mode: 'lines+markers',
                    line: { color: lineColor, width: 2 },
                    marker: { size: 5 },
                    hovertemplate: `%{customdata[0]}<br>${name}: %{y:.0f}${unitLabel}<extra></extra>`
                },
            ];
        }

        const traces = [
            ...bandTraces('temp', 'Temperature', '#dc2626', 'rgba(220,38,38,0.15)'),
            ...bandTraces('dewpoint', 'Dewpoint', '#0369a1', 'rgba(3,105,161,0.15)'),
        ];

        plotChart('temperatureChart', traces, chartLayout(axis, {
            height: 340,
            mobileHeight: 260,
            yTitle: `Degrees ${tempUnit === 'C' ? 'Celsius' : 'Fahrenheit'}`,
            yaxis: { zeroline: false },
        }));
    }

    // Sequential-by-severity categorical colors for precipitation type
    const PRECIP_TYPE_COLORS = {
        'Thunderstorm': '#f59e0b',
        'Freezing': '#7c3aed',
        'Snow/Ice': '#0d9488',
        'Rain': '#2563eb',
        'Drizzle': '#7dd3fc',
        'Other / Unspecified': '#9ca3af',
    };

    // Stacked bars of precipitation frequency per column, broken down by type.
    // Frequencies rather than counts: columns don't all have the same number
    // of samples (months in the fetch window get 3 or 4 years of data, and
    // part-time airports report fewer night hours), so raw counts would make
    // better-sampled columns look wetter.
    function displayPrecipitationChart(precipitation, axis) {
        const stats = axis.keys.map(k => precipitation.periods[k] || null);

        const summaries = stats.map(s => {
            if (!s || s.count === 0) return 'No precipitation recorded';
            const hourWord = s.count === 1 ? 'hour' : 'hours';
            let text = `Measurable precipitation in ${(s.freq * 100).toFixed(1)}%` +
                ` of this ${axis.periodNoun}'s samples (${s.count} ${hourWord})`;
            if (s.median_in !== null) {
                text += `, typically ${s.median_in.toFixed(2)} in`;
            }
            return text;
        });

        const traces = precipitation.types.map(type => ({
            x: axis.x,
            y: stats.map(s => s ? s.type_freq[type] : 0),
            // customdata rows: [column label, this type's count, column summary]
            customdata: stats.map((s, i) =>
                [axis.hoverLabels[i], s ? s.type_count[type] : 0, summaries[i]]),
            name: type,
            type: 'bar',
            marker: { color: PRECIP_TYPE_COLORS[type] },
            hovertemplate: `%{customdata[0]}<br>${type}: %{y:.1%} (%{customdata[1]})` +
                '<br>%{customdata[2]}<extra></extra>'
        }));

        // Tallest stacked bar (total frequency per column), for the y-axis ceiling
        const maxFreq = Math.max(0, ...stats.map(s => s ? s.freq : 0));

        plotChart('precipitationChart', traces, chartLayout(axis, {
            height: 300,
            mobileHeight: 240,
            yTitle: `Fraction of ${axis.sampleUnit}`,
            yaxis: {
                // '~' trims trailing zeros, so small ranges get "0.5%" ticks
                // rather than ".0%" rounding them into duplicate "0% 0% 1%"
                tickformat: '.1~%',
                // rangemode 'tozero' isn't enough when every value is 0 (Plotly
                // still autoscales to an arbitrary range), so pin an explicit
                // floor and give a little headroom above the tallest bar
                rangemode: 'tozero',
                range: [0, Math.max(0.01, maxFreq) * 1.15],
            },
            barmode: 'stack',
        }));
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
