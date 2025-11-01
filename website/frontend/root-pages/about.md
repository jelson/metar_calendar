---
layout: infopage
title: About the Metar Predictor
permalink: /about/
---

<style>
.vfr { color: #22c55e; font-weight: 600; }
.mvfr { color: #3b82f6; font-weight: 600; }
.ifr { color: #ef4444; font-weight: 600; }
.lifr { color: #a855f7; font-weight: 600; }
</style>

Have you ever planned a flight into a coastal airport and wondered, "What time will this marine layer burn off if I fly in next week?" TAFs only go out a day or two in advance. If you're planning an itinerary for next week or next month, it's hard to know what to expect.

This predictor is my attempt to solve that problem. Given an airport of interest, it downloads historical METAR data and counts how often the airport was VFR, MVFR, IFR, or LIFR at each hour of the day. Because weather depends on the season, if you're interested in October, the prediction is based on the last several Octobers of data. The output is a stacked bar chart showing all 24 hours of the day, color-coded to show how often each flight condition occurred during that hour.

For example, the chart below shows the prediction for Santa Monica Airport (KSMO) in June—special to me, because I learned to fly at that coastal airport in Southern California over 20 years ago and was often bedeviled by [June Gloom](https://en.wikipedia.org/wiki/June_Gloom).

![KSMO June weather prediction](/assets/images/KSMO-06.png)

**How to read the chart:** Each bar represents one hour of the day (UTC). The height of each colored section shows the percentage of days in that month that had that flight condition during that hour. <span class="vfr">VFR</span> is stacked on the bottom, making it easy to read—just look at where the green ends. For example, at hour 0 UTC (5 PM local), the <span class="vfr">VFR</span> section extends from 0 to 0.70, meaning 70% of days in past Junes had VFR conditions at 5 PM. Above that, <span class="mvfr">MVFR</span> goes from 0.70 to 0.90 (20%), <span class="ifr">IFR</span> from 0.90 to 0.98 (8%), and <span class="lifr">LIFR</span> from 0.98 to 1.0 (2%). By hour 8 UTC (1 AM local), the <span class="vfr">VFR</span> bar is much shorter—from 0 to 0.27—indicating only a 27% chance of VFR, with a 73% chance of marine layer: 35% <span class="mvfr">MVFR</span>, 27% <span class="ifr">IFR</span>, and 12% <span class="lifr">LIFR</span>.

**KSMO in June** shows classic June Gloom. The best predicted conditions are from 20-23 UTC (1-4 PM local) with 76-87% <span class="vfr">VFR</span>. The worst marine layer hits from 7-15 UTC (midnight-8 AM local). At the worst hours (13-14 UTC / 6-7 AM local), <span class="vfr">VFR</span> is only 22-27%, with a 73-78% chance of marine layer: 50-53% <span class="mvfr">MVFR</span>, 15-22% <span class="ifr">IFR</span>, and 5-7% <span class="lifr">LIFR</span>. The marine layer begins burning off at 16-18 UTC (9-11 AM local) with <span class="vfr">VFR</span> improving from 43% to 58%.

Van Nuys Airport (KVNY) was often our planned alternate. Even though it's just 14 miles away,  its weather is consistently better than Santa Monica due to being further inland and protected from the marine layer by the Santa Monica Mountains. The predictor confirms this:

![KVNY June weather prediction](/assets/images/KVNY-06.png)

**KVNY in June** shows substantially better conditions. The best chance at <span class="vfr">VFR</span> is from 19 UTC through 6 UTC (noon through 11 PM local) at 79-93%. The marine layer affects KVNY from 7-16 UTC (midnight-9 AM local), but is noticeably lighter than KSMO. At the worst hours (13-14 UTC / 6-7 AM local), <span class="vfr">VFR</span> is still 38-39% likely with a 61-62% marine layer (29-30% <span class="mvfr">MVFR</span>, 22% <span class="ifr">IFR</span>, and 10% <span class="lifr">LIFR</span>)—significantly better than KSMO's 22-27% <span class="vfr">VFR</span> and 73-78% marine layer at the same hours. This validates what we knew from experience: when KSMO was socked in, KVNY was usually a safe bet.

Of course, the best way to escape June Gloom at Santa Monica is not to divert to Van Nuys, but to wait until August:

![KSMO August weather prediction](/assets/images/KSMO-08.png)

**KSMO in August** has much better weather than it does in June. The best <span class="vfr">VFR</span> is from 18-23 UTC (11 AM-4 PM local) at 94-98%. The marine layer is much lighter and later than June, affecting mainly 10-15 UTC (3-8 AM local). At the worst hours (12-13 UTC / 5-6 AM local), <span class="vfr">VFR</span> is still 52-55% with only a 45-48% marine layer (19-23% <span class="mvfr">MVFR</span>, 19-21% <span class="ifr">IFR</span>, and 5-6% <span class="lifr">LIFR</span>)—a significant improvement over June's 22% <span class="vfr">VFR</span> at the same hours.

## How It Works

The predictor downloads several years of historical METAR data from the [Iowa Environmental Mesonet ASOS network](https://mesonet.agron.iastate.edu/request/download.phtml) for your selected airport and month, then calculates the fraction of observations that fall into each flight condition (VFR, MVFR, IFR, LIFR) for each hour of the day. The stacked bar chart makes it easy to see patterns like morning marine layers, afternoon thunderstorms, or consistently good (or bad) conditions.

Flight conditions are determined by ceiling and visibility, with the more restrictive condition defining the overall flight condition:

| Condition | Ceiling | Visibility |
|-----------|---------|------------|
| **VFR** | ≥ 3,000 ft AGL | ≥ 5 statute miles |
| **MVFR** | ≥ 1,000 and < 3,000 ft AGL | ≥ 3 and < 5 statute miles |
| **IFR** | ≥ 500 and < 1,000 ft AGL | ≥ 1 and < 3 statute miles |
| **LIFR** | < 500 ft AGL | < 1 statute mile |

## Using the Predictor

Select a month, search for an airport by its code (ICAO or IATA) or name, and click Go to view the predicted hourly conditions for that location.

The autocomplete search prioritizes exact code matches first, followed by airports whose names start with your search term. For example, typing NEW matches Lakefront Airport (KNEW) first, followed by airports whose names begin with "New" such as Newark and Newport. The search is fuzzy and typo-tolerant, so even partial or slightly misspelled queries will find relevant results.

**Note:** The autocomplete only shows airports that have historical METAR data available. Our database includes approximately 4,300 airports with weather data out of the 80,000+ airports worldwide from [OurAirports](https://ourairports.com/data/). If your airport doesn't appear in the search, it is likely because there's no historical METAR data available for it from the [Iowa Environmental Mesonet](https://mesonet.agron.iastate.edu/).
