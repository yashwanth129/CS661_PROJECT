let diseaseHierarchy = {};
let locationData = {};
let availableYears = [];
let selectedDiseases = new Set();
let selectedSexes = new Set([1, 2]);
let currentYear = null;
let worldData;
let colorScale;
let isPlaying = false;
let playInterval = null;
let animationSpeed = 1000; // 1 second per year
let countryRatesData = {}; 
let allYearsDataCache = {};
let isDataLoading = false;
let countryHistoryCache = {};

document.addEventListener('DOMContentLoaded', function() {
    Promise.all([d3.json('/api/diseases'),d3.json('/api/locations'),d3.json('/api/years'),d3.json('https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json')])
    .then(([diseases, locations, years, world]) => {
        diseaseHierarchy = diseases;
        locationData = locations;
        availableYears = years;
        worldData = world;
        currentYear = availableYears[availableYears.length - 1];
        initializeSexFilter();
        initializeDiseaseTree();
        initializeMap();
        initializeTimeline();
        updateYearDisplay();
    }).catch(error => console.error('Error loading data:', error));
});

function getSelectionKey() {
    const diseases = Array.from(selectedDiseases).sort().join(',');
    const sexes = Array.from(selectedSexes).sort().join(',');
    return `${diseases}|${sexes}`;
}

async function fetchCountryHistory(locationId) {
    const selectionKey = getSelectionKey();
    const cacheKey = `${locationId}|${selectionKey}`;
    if (countryHistoryCache[cacheKey]) {
        return countryHistoryCache[cacheKey];
    }
    const diseases = Array.from(selectedDiseases).join(',');
    const sexes = Array.from(selectedSexes).join(',');
    const url = `/api/country-history?location=${locationId}&diseases=${diseases}&sexes=${sexes}`;
    
    try {
        const response = await d3.json(url);
        countryHistoryCache[cacheKey] = response;
        return response;
    } catch (error) {
        console.error('Error fetching country history:', error);
        return null;
    }
}
function createLineGraph(data, container, width, height) {
    container.html("");
    const svg = container.append('svg')
        .attr('width', width)
        .attr('height', height);
    const margin = {top: 10, right: 40, bottom: 30, left: 40};
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    const chart = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);
    const years = Object.keys(data.total || {}).map(Number).sort((a, b) => a - b);
    if (years.length === 0) return;
    let allValues = [];
    years.forEach(year => {
        const yearStr = year.toString();
        if (data.total && data.total[yearStr]) allValues.push(parseFloat(data.total[yearStr]));
    });
    
    const x = d3.scaleLinear()
        .domain([d3.min(years), d3.max(years)])
        .range([0, innerWidth]);
    
    const y = d3.scaleLinear()
        .domain([0, d3.max(allValues) * 1.1]) // Add 10% padding on top
        .range([innerHeight, 0]);
    
    const xAxis = d3.axisBottom(x)
        .ticks(Math.min(years.length, 5))
        .tickFormat(d3.format('d'));
    
    const yAxis = d3.axisLeft(y)
        .ticks(5)
        .tickFormat(d => d.toFixed(1));
    chart.append('g')
        .attr('class', 'line-graph-axis x-axis')
        .attr('transform', `translate(0,${innerHeight})`)
        .call(xAxis);
    
    chart.append('g')
        .attr('class', 'line-graph-axis y-axis')
        .call(yAxis);
    
    const line = d3.line()
        .x(d => x(d.year))
        .y(d => y(d.value));
    
    chart.append('line')
        .attr('x1', x(currentYear))
        .attr('x2', x(currentYear))
        .attr('y1', 0)
        .attr('y2', innerHeight)
        .attr('stroke', '#000')
        .attr('stroke-width', 1)
        .attr('stroke-dasharray', '3,3')
        .attr('opacity', 0.5);
    
    if (data.total) {
        const totalData = years.map(year => ({
            year: year,
            value: parseFloat(data.total[year.toString()] || 0)
        }));
        
        chart.append('path')
            .datum(totalData)
            .attr('fill', 'none')
            .attr('stroke', '#000')
            .attr('stroke-width', 3)
            .attr('d', line);
    }
        
    const legend = chart.append('g')
        .attr('class', 'line-legend')
        .attr('transform', `translate(${innerWidth - 60}, 5)`);
    
    legend.append('line')
        .attr('x1', 0)
        .attr('x2', 15)
        .attr('y1', 5)
        .attr('y2', 5)
        .attr('stroke', '#000')
        .attr('stroke-width', 2);
    
    legend.append('text')
        .attr('x', 20)
        .attr('y', 9)
        .text('Total')
        .style('font-size', '8px');
}

async function loadAllYearsData() {
    const selectionKey = getSelectionKey();
    
    if (allYearsDataCache[selectionKey]) {
        return allYearsDataCache[selectionKey];
    }
    
    setLoadingState(true);
    
    try {
        const diseases = Array.from(selectedDiseases).join(',');
        const sexes = Array.from(selectedSexes).join(',');
        
        const url = `/api/all-years-data?diseases=${diseases}&sexes=${sexes}`;
        const response = await d3.json(url);
        allYearsDataCache[selectionKey] = response;
        return response;
    } catch (error) {
        console.error('Error fetching all years data:', error);
        return null;
    } finally {
        setLoadingState(false);
    }
}

function setLoadingState(isLoading) {
    const playButton = d3.select('#play-button');
    const playText = playButton.select('.play-text');
    const loader = playButton.select('.loader');
    isDataLoading = isLoading;
    
    playButton.property('disabled', isLoading);
    
    if (isLoading) {
        playText.style('display', 'none');
        loader.style('display', 'inline-block');
    } else {
        playText.style('display', 'inline-block');
        loader.style('display', 'none');
        playText.text(isPlaying ? 'Pause' : 'Play');
    }
}

function initializeSexFilter() {
    d3.selectAll('.sex-checkbox').on('change', function() {
        selectedSexes.clear();
        d3.selectAll('.sex-checkbox:checked').each(function() {
            selectedSexes.add(parseInt(d3.select(this).attr('data-sex')));
        });

        if (selectedSexes.size === 0) {
            selectedSexes.add(1);
            selectedSexes.add(2);
            d3.selectAll('.sex-checkbox').property('checked', true);
        }
        countryHistoryCache = {};
        
        updateMap();
    });
}
function initializeDiseaseTree() {
    const treeContainer = d3.select('#disease-tree');
    
    const rootItems = diseaseHierarchy.causes;
    renderDiseaseLevel(treeContainer, rootItems, true);
}

function renderDiseaseLevel(container, items, isCollapsed) {
    items.forEach(item => {
        const itemContainer = container.append('div')
            .attr('class', 'disease-item')
            .attr('data-id', item.id);
        
        const hasChildren = item.subcauses && item.subcauses.length > 0;

        if (hasChildren) {
            itemContainer.append('span')
                .attr('class', 'toggle-icon')
                .html(isCollapsed ? '▶' : '▼')
                .on('click', function() {
                    const isCurrentlyCollapsed = d3.select(this).html() === '▶';
                    d3.select(this).html(isCurrentlyCollapsed ? '▼' : '▶');
                    
                    const childrenContainer = d3.select(this.parentNode)
                        .select('.disease-children');
                    
                    childrenContainer.style('display', isCurrentlyCollapsed ? 'block' : 'none');
                });
        } else {
            itemContainer.append('span')
                .attr('class', 'toggle-icon')
                .html('&nbsp;');
        }
        const checkboxContainer = itemContainer.append('span');
        
        const checkbox = checkboxContainer.append('input')
            .attr('type', 'checkbox')
            .attr('class', 'checkbox')
            .attr('id', `disease-${item.id}`)
            .attr('data-id', item.id)
            .on('change', function() {
                const isChecked = d3.select(this).property('checked');
                if (isChecked) {
                    addDiseaseAndChildren(item);
                } else {
                    removeDiseaseAndChildren(item);
                }
                updateChildCheckboxes(item, isChecked);
                allYearsDataCache = {};
                countryHistoryCache = {};
                updateMap();
            });
        checkboxContainer.append('label')
            .attr('for', `disease-${item.id}`)
            .text(`${item.name} (${item.cause})`);
        if (hasChildren) {
            const childrenContainer = itemContainer.append('div')
                .attr('class', 'disease-children')
                .style('display', isCollapsed ? 'none' : 'block');            
            renderDiseaseLevel(childrenContainer, item.subcauses, true);
        }
    });
}

function updateChildCheckboxes(item, isChecked) {
    if (item.subcauses && item.subcauses.length > 0) {
        item.subcauses.forEach(child => {
            d3.select(`#disease-${child.id}`).property('checked', isChecked);
            updateChildCheckboxes(child, isChecked);
        });
    }
}

function addDiseaseAndChildren(disease) {
    selectedDiseases.add(parseInt(disease.id));    
    if (disease.subcauses && disease.subcauses.length > 0) {
        disease.subcauses.forEach(child => {
            addDiseaseAndChildren(child);
        });
    }
}

function removeDiseaseAndChildren(disease) {
    selectedDiseases.delete(parseInt(disease.id));    
    if (disease.subcauses && disease.subcauses.length > 0) {
        disease.subcauses.forEach(child => {
            removeDiseaseAndChildren(child);
        });
    }
}

function initializeMap() {
    const width = document.getElementById('map-container').offsetWidth;
    const height = document.getElementById('map-container').offsetHeight;
    
    const svg = d3.select('#map-container')
        .append('svg')
        .attr('width', width)
        .attr('height', height);
    const projection = d3.geoNaturalEarth1()
        .scale(width / 2 / Math.PI)
        .translate([width / 2, height / 2]);
    const path = d3.geoPath()
        .projection(projection);
    let tooltip = d3.select('#tooltip');
    if (tooltip.empty()) {
        tooltip = d3.select('body').append('div')
            .attr('id', 'tooltip')
            .attr('class', 'tooltip')
            .style('opacity', 0);
    }
    const countries = topojson.feature(worldData, worldData.objects.countries).features;
    const locationIdToName = {};
    for (const [id, name] of Object.entries(locationData)) {
        locationIdToName[id] = name;
    }
    const countryToLocationId = {};
    countries.forEach(country => {
        for (const [locId, locName] of Object.entries(locationData)) {
            if (country.properties.name && locName &&
                (country.properties.name.toLowerCase().includes(locName.toLowerCase()) || 
                 locName.toLowerCase().includes(country.properties.name.toLowerCase()))) {
                countryToLocationId[country.id] = locId;
                break;
            }
        }
    });
    
    svg.selectAll('path')
        .data(countries)
        .enter()
        .append('path')
        .attr('d', path)
        .attr('class', 'country')
        .attr('fill', '#ccc')
        .attr('stroke', '#fff')
        .attr('stroke-width', 0.5)
        .attr('data-id', d => countryToLocationId[d.id])
        .on('click', function(event, d) {
            const locationId = d3.select(this).attr('data-id');
            if (!locationId) return;
            const selectedDiseasesParam = Array.from(selectedDiseases).join(',');
            const selectedSexesParam = Array.from(selectedSexes).join(',');
            const url = `/country/${locationId}?diseases=${selectedDiseasesParam}&sexes=${selectedSexesParam}`;
            window.location.href = url;
        })

        .on('mouseover', async function(event, d) {
            const locationId = countryToLocationId[d.id];
            if (!locationId) return;
            
            const countryName = locationData[locationId];
            const countryData = countryRatesData[locationId] || {};
            const maleRate = countryData["1"] || 0;
            const femaleRate = countryData["2"] || 0;
            const totalRate = countryData.total || 0;

            tooltip.transition()
                .duration(200)
                .style('opacity', 0.9);
            
            tooltip.html(`
                <div class="tooltip-title">${countryName}</div>
                <div class="tooltip-loading">Loading historical data...</div>
                <div class="tooltip-details">
                    <div>Year: ${currentYear}</div>
                    <div>Total Rate: ${totalRate.toFixed(2)}</div>
                    ${selectedSexes.has(1) ? `<div>Male Rate: ${maleRate.toFixed(2)}</div>` : ''}
                    ${selectedSexes.has(2) ? `<div>Female Rate: ${femaleRate.toFixed(2)}</div>` : ''}
                </div>
            `)
            .style('left', (event.pageX + 15) + 'px')
            .style('top', (event.pageY - 30) + 'px');
            
            const historyData = await fetchCountryHistory(locationId);
            
            if (historyData) {
                tooltip.html(`
                    <div class="tooltip-title">${countryName}</div>
                    <div class="tooltip-graph"></div>
                    <div class="tooltip-details">
                        <div>Year: ${currentYear}</div>
                        <div>Rate: ${totalRate.toFixed(2)}</div>
                    </div>
                `);
                createLineGraph(historyData, tooltip.select('.tooltip-graph'), 250, 150);
            }
        })
        .on('mousemove', function(event) {
            tooltip
                .style('left', (event.pageX + 15) + 'px')
                .style('top', (event.pageY - 30) + 'px');
        })
        .on('mouseout', function() {
            tooltip.transition()
                .duration(500)
                .style('opacity', 0);
        });
    
    const zoom = d3.zoom()
        .scaleExtent([1, 8])
        .on('zoom', (event) => {
            svg.selectAll('path')
                .attr('transform', event.transform);
        });
    
    svg.call(zoom);
    createLegend();
    updateMap();
}

function createLegend() {
    const legendContainer = d3.select('#legend-container');
    const width = 300;
    const height = 20;
    
    const svg = legendContainer.append('svg')
        .attr('width', width)
        .attr('height', 40);
    const gradient = svg.append('defs')
        .append('linearGradient')
        .attr('id', 'legend-gradient')
        .attr('x1', '0%')
        .attr('y1', '0%')
        .attr('x2', '100%')
        .attr('y2', '0%');
    gradient.append('stop')
        .attr('offset', '0%')
        .attr('stop-color', d3.interpolateYlOrRd(0));
    gradient.append('stop')
        .attr('offset', '100%')
        .attr('stop-color', d3.interpolateYlOrRd(1));
    
    svg.append('rect')
        .attr('x', 0)
        .attr('y', 0)
        .attr('width', width)
        .attr('height', height)
        .style('fill', 'url(#legend-gradient)');
    svg.append('text')
        .attr('class', 'legend-min')
        .attr('x', 5)
        .attr('y', height + 15)
        .style('font-size', '12px')
        .text('Min: 0.00');
    svg.append('text')
        .attr('class', 'legend-max')
        .attr('x', width - 5)
        .attr('y', height + 15)
        .attr('text-anchor', 'end')
        .style('font-size', '12px')
        .text('Max: 0.00');
}

function updateLegend(min, max) {
    d3.select('.legend-min').text(`Min: ${min.toFixed(2)}`);
    d3.select('.legend-max').text(`Max: ${max.toFixed(2)}`);
}

function initializeTimeline() {
    const container = d3.select('#timeline-slider');
    const margin = {top: 10, right: 50, bottom: 25, left: 50};
    const width = container.node().getBoundingClientRect().width - margin.left - margin.right;
    const height = 40;
    const svg = container.append('svg')
        .attr('width', width + margin.left + margin.right)
        .attr('height', height + margin.top + margin.bottom)
        .append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);
    const x = d3.scaleLinear()
        .domain([d3.min(availableYears), d3.max(availableYears)])
        .range([0, width])
        .clamp(true);

    svg.append('line')
        .attr('class', 'track')
        .attr('x1', x.range()[0])
        .attr('x2', x.range()[1])
        .attr('y1', height / 2)
        .attr('y2', height / 2);
        
    svg.append('line')
        .attr('class', 'track-inset')
        .attr('x1', x.range()[0])
        .attr('x2', x.range()[1])
        .attr('y1', height / 2)
        .attr('y2', height / 2);
    svg.selectAll('.year-tick')
        .data(availableYears)
        .enter()
        .append('line')
        .attr('class', 'year-tick')
        .attr('x1', d => x(d))
        .attr('x2', d => x(d))
        .attr('y1', height / 2 - 5)
        .attr('y2', height / 2 + 5);
    
    svg.selectAll('.year-label')
        .data([availableYears[0], availableYears[availableYears.length - 1]])
        .enter()
        .append('text')
        .attr('class', 'year-label')
        .attr('x', d => x(d))
        .attr('y', height / 2 + 20)
        .text(d => d);
    
    svg.selectAll('.year-dot')
        .data(availableYears.slice(1, availableYears.length - 1))
        .enter()
        .append('circle')
        .attr('class', 'year-dot')
        .attr('cx', d => x(d))
        .attr('cy', height / 2)
        .attr('r', 3);
    
    const handle = svg.append('circle')
        .attr('class', 'handle')
        .attr('r', 8)
        .attr('cx', x(currentYear))
        .attr('cy', height / 2);

    const overlay = svg.append('rect')
        .attr('class', 'track-overlay')
        .attr('width', width)
        .attr('height', height)
        .attr('x', 0)
        .attr('y', 0)
        .style('opacity', 0)
        .style('pointer-events', 'all')
        .call(d3.drag()
            .on('start.interrupt', function() { handle.interrupt(); })
            .on('start drag', function(event) {
                const yearValue = x.invert(event.x);
                const closestYear = availableYears.reduce((prev, curr) => {
                    return (Math.abs(curr - yearValue) < Math.abs(prev - yearValue) ? curr : prev);
                });
                
                handle.attr('cx', x(closestYear));
                if (currentYear !== closestYear) {
                    currentYear = closestYear;
                    updateYearDisplay();
                    updateMapWithYearData(currentYear);
                }
            })
        )
        .on('mousemove', function(event) {
            const xPos = d3.pointer(event)[0];
            const year = Math.round(x.invert(xPos));
            const closestYear = availableYears.reduce((prev, curr) => 
                Math.abs(curr - year) < Math.abs(prev - year) ? curr : prev
            );
            const yearDotX = x(closestYear);
            const distanceToYearDot = Math.abs(xPos - yearDotX);
            if (distanceToYearDot <= 8) {
                const tooltip = d3.select('#tooltip');
                if (tooltip.empty()) {
                    d3.select('body').append('div')
                        .attr('id', 'tooltip')
                        .attr('class', 'tooltip')
                        .style('opacity', 0);
                }
                
                d3.select('#tooltip')
                    .transition()
                    .duration(200)
                    .style('opacity', 0.9);
                
                d3.select('#tooltip')
                    .html(`<div class="tooltip-title">Year: ${closestYear}</div>`)
                    .style('left', (event.pageX + 10) + 'px')
                    .style('top', (event.pageY - 28) + 'px');
                
                svg.selectAll('.year-dot')
                    .attr('r', d => d === closestYear ? 6 : 4)
                    .attr('fill', d => d === closestYear ? '#333' : '#555');
            } else {
                d3.select('#tooltip')
                    .transition()
                    .duration(500)
                    .style('opacity', 0);
                svg.selectAll('.year-dot')
                    .attr('r', 4)
                    .attr('fill', '#555');
            }
        });
    d3.select('#play-button').on('click', togglePlay);
    updateYearDisplay();
}
function updateYearDisplay() {
    d3.select('#current-year-display').text(`Year: ${currentYear}`);
}
async function togglePlay() {
    if (isDataLoading) return;
    isPlaying = !isPlaying;
    
    if (isPlaying) {
        const allYearsData = await loadAllYearsData();
        if (!allYearsData) {
            isPlaying = false;
            setLoadingState(false);
            return;
        }
        
        d3.select('#play-button .play-text').text('Pause');
        startAnimation();
    } else {
        d3.select('#play-button .play-text').text('Play');
        stopAnimation();
    }
}

function startAnimation() {
    stopAnimation();
    let yearIndex = availableYears.indexOf(currentYear);
    if (yearIndex === availableYears.length - 1) {
        yearIndex = 0;
        currentYear = availableYears[yearIndex];
        updateTimelineHandle();
        updateYearDisplay();
        updateMapWithYearData(currentYear);
    }
    playInterval = setInterval(() => {
        yearIndex++;
        if (yearIndex >= availableYears.length) {
            yearIndex = 0;
        }
        
        currentYear = availableYears[yearIndex];
        updateTimelineHandle();
        updateYearDisplay();
        updateMapWithYearData(currentYear);
        
        if (yearIndex === 0) {
            stopAnimation();
            d3.select('#play-button .play-text').text('Play');
            isPlaying = false;
        }
    }, animationSpeed);
}

function stopAnimation() {
    if (playInterval) {
        clearInterval(playInterval);
        playInterval = null;
    }
}

function updateTimelineHandle() {
    const x = d3.scaleLinear()
        .domain([d3.min(availableYears), d3.max(availableYears)])
        .range([0, d3.select('#timeline-slider svg').node().getBoundingClientRect().width - 100])
        .clamp(true);
    
    d3.select('.handle')
        .transition()
        .duration(animationSpeed / 2)
        .attr('cx', x(currentYear));
}

async function updateMap() {
    if (selectedDiseases.size === 0 || selectedSexes.size === 0) {
        d3.selectAll('.country').attr('fill', '#ccc');
        updateLegend(0, 0);
        countryRatesData = {};
        return;
    }
    
    const url = `/api/all-countries-rates?year=${currentYear}&diseases=${Array.from(selectedDiseases).join(',')}&sexes=${Array.from(selectedSexes).join(',')}`;
    
    try {
        const data = await d3.json(url);
        countryRatesData = data;
        const stats = data._statistics || { min: 0, max: 1 };
        delete data._statistics;
        updateLegend(stats.min, stats.max);
        colorScale = d3.scaleSequential(d3.interpolateYlOrRd)
            .domain([0, stats.max || 1]);
        d3.selectAll('.country')
            .transition()
            .duration(animationSpeed / 2)
            .attr('fill', function() {
                const locationId = d3.select(this).attr('data-id');
                if (!locationId) return '#ccc';
                const countryData = countryRatesData[locationId];
                return countryData && countryData.total ? 
                       colorScale(countryData.total) : '#ccc';
            });
    } catch (error) {
        console.error('Error fetching rates by country:', error);
    }
}

function updateMapWithYearData(year) {
    const yearStr = year.toString();
    const selectionKey = getSelectionKey();
    if (!allYearsDataCache[selectionKey] || !allYearsDataCache[selectionKey].yearData[yearStr]) {
        updateMap();
        return;
    }
    const data = allYearsDataCache[selectionKey].yearData[yearStr];
    const stats = allYearsDataCache[selectionKey].statistics[yearStr];
    countryRatesData = data;
    updateLegend(stats.min, stats.max);
    colorScale = d3.scaleSequential(d3.interpolateYlOrRd)
        .domain([0, stats.max || 1]);
    d3.selectAll('.country')
        .transition()
        .duration(animationSpeed / 2)
        .attr('fill', function() {
            const locationId = d3.select(this).attr('data-id');
            if (!locationId) return '#ccc';
            
            const countryData = data[locationId];
            return countryData && countryData.total ? 
                   colorScale(countryData.total) : '#ccc';
        });
}
