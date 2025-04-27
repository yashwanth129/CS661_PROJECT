let diseaseHierarchy = {};
let locationData = {};
let availableYears = [];
let selectedDiseases = new Set();
let selectedSexes = new Set([1, 2]);
let level1DiseaseData = {};
let level1Diseases = {};
let level1Children = {};
let colorScale = d3.scaleOrdinal(d3.schemeCategory10);

function parseUrlParams() {
    const urlParams = new URLSearchParams(window.location.search);
    const diseasesParam = urlParams.get('diseases');
    if (diseasesParam) {
        diseasesParam.split(',').forEach(id => {
            if (id) selectedDiseases.add(parseInt(id));
        });
    }
    const sexesParam = urlParams.get('sexes');
    if (sexesParam) {
        selectedSexes.clear();
        sexesParam.split(',').forEach(id => {
            if (id) selectedSexes.add(parseInt(id));
        });
        d3.select('#male-checkbox').property('checked', selectedSexes.has(1));
        d3.select('#female-checkbox').property('checked', selectedSexes.has(2));
    }
}

document.addEventListener('DOMContentLoaded', function() {
    parseUrlParams();
    
    Promise.all([
        d3.json('/api/diseases'),
        d3.json('/api/locations'),
        d3.json('/api/years')
    ]).then(([diseases, locations, years]) => {
        diseaseHierarchy = diseases;
        locationData = locations;
        availableYears = years;
        extractLevel1Diseases(diseaseHierarchy.causes);
        initializeSexFilter();
        initializeDiseaseTree();
        loadDiseaseData();
        setupBackButton();
    }).catch(error => console.error('Error loading data:', error));
});

function extractLevel1Diseases(causes) {
    causes.forEach(cause => {
        if (cause.cause && cause.cause.length === 1) {
            level1Diseases[cause.id] = cause.name;
            level1Children[cause.id] = new Set();
            if (cause.subcauses) {
                addChildrenRecursively(cause.id, cause.subcauses);
            }
        }
    });
}
function addChildrenRecursively(parentId, subcauses) {
    subcauses.forEach(subcause => {
        level1Children[parentId].add(parseInt(subcause.id));
        
        if (subcause.subcauses) {
            addChildrenRecursively(parentId, subcause.subcauses);
        }
    });
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
        loadDiseaseData();
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
                .html(' ');
        }
        const checkboxContainer = itemContainer.append('span');
        const checkbox = checkboxContainer.append('input')
            .attr('type', 'checkbox')
            .attr('class', 'checkbox')
            .attr('id', `disease-${item.id}`)
            .attr('data-id', item.id)
            .property('checked', selectedDiseases.has(parseInt(item.id)))
            .on('change', function() {
                const isChecked = d3.select(this).property('checked');
                if (isChecked) {
                    addDiseaseAndChildren(item);
                } else {
                    removeDiseaseAndChildren(item);
                }
                updateChildCheckboxes(item, isChecked);
                loadDiseaseData();
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
function loadDiseaseData() {
    d3.select('#line-chart-container')
        .html('<div class="loading-indicator">Loading disease data...</div>');
    const diseases = Array.from(selectedDiseases).join(',');
    const sexes = Array.from(selectedSexes).join(',');
    const url = `/api/disease-rates-by-level1?location=${locationId}&diseases=${diseases}&sexes=${sexes}`;
    
    d3.json(url).then(data => {
        level1DiseaseData = data;
        createLineChart();
    }).catch(error => {
        console.error('Error loading disease data:', error);
        d3.select('#line-chart-container')
            .html('<div class="error-message">Error loading disease data</div>');
    });
}

function createLineChart() {
    const container = d3.select('#line-chart-container');
    container.html('');
    
    const width = container.node().offsetWidth;
    const height = 500;
    const margin = { top: 40, right: 120, bottom: 60, left: 80 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    
    if (Object.keys(level1DiseaseData).length === 0) {
        container.html('<div class="no-data-message">No data available for selected diseases and sexes</div>');
        return;
    }
    
    const svg = container.append('svg')
        .attr('width', width)
        .attr('height', height);
    
    const chart = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);
    
    const allYears = new Set();
    Object.values(level1DiseaseData).forEach(disease => {
        Object.keys(disease.data).forEach(year => {
            allYears.add(parseInt(year));
        });
    });
    
    const years = Array.from(allYears).sort((a, b) => a - b);
    if (years.length === 0) {
        chart.append('text')
            .attr('x', innerWidth / 2)
            .attr('y', innerHeight / 2)
            .attr('text-anchor', 'middle')
            .text('No data available for selected diseases and sexes');
        return;
    }
    let maxValue = 0;
    Object.values(level1DiseaseData).forEach(disease => {
        Object.values(disease.data).forEach(yearData => {
            const total = yearData.total || 0;
            maxValue = Math.max(maxValue, total);
        });
    });
    const x = d3.scaleLinear()
        .domain([d3.min(years), d3.max(years)])
        .range([0, innerWidth]);
    
    const y = d3.scaleLinear()
        .domain([0, maxValue * 1.1])
        .range([innerHeight, 0]);
    const labelFrequency = Math.max(1, Math.floor(years.length / 5));
    const xAxis = d3.axisBottom(x)
        .tickValues(years)
        .tickFormat((d, i) => {
            return i % labelFrequency === 0 ? d3.format('d')(d) : '';
        });
    
    const yAxis = d3.axisLeft(y)
        .ticks(10);
    let tooltip = d3.select('#tooltip');
    if (tooltip.empty()) {
        tooltip = d3.select('body').append('div')
            .attr('id', 'tooltip')
            .attr('class', 'tooltip')
            .style('opacity', 0);
    }
    
    const xAxisGroup = chart.append('g')
        .attr('class', 'x-axis')
        .attr('transform', `translate(0,${innerHeight})`)
        .call(xAxis);
        
    xAxisGroup.selectAll('.tick line')
        .attr('stroke-width', 2)
        .attr('y2', 8);
        
    xAxisGroup.selectAll('.tick')
        .style('cursor', 'pointer')
        .on('mouseover', function(event, d) {
            tooltip.html(`<div class="tooltip-details">Year: ${d}</div>`)
                .style('left', (event.pageX + 10) + 'px')
                .style('top', (event.pageY - 20) + 'px')
                .style('opacity', 1);
        })
        .on('mouseout', function() {
            tooltip.style('opacity', 0);
        })
        .on('click', function(event, d) {
            createSunburstChart(d);
        });
    
    chart.append('g')
        .attr('class', 'y-axis')
        .call(yAxis);
    chart.append('text')
        .attr('class', 'x-axis-label')
        .attr('x', innerWidth / 2)
        .attr('y', innerHeight + 40)
        .attr('text-anchor', 'middle')
        .text('Year');
    
    chart.append('text')
        .attr('class', 'y-axis-label')
        .attr('transform', 'rotate(-90)')
        .attr('x', -innerHeight / 2)
        .attr('y', -60)
        .attr('text-anchor', 'middle')
        .text('Rate per 100,000');
    
    const line = d3.line()
        .x(d => x(d.year))
        .y(d => y(d.value))
        .curve(d3.curveMonotoneX);
    const linesGroup = chart.append('g')
        .attr('class', 'lines-group');
    const hoverGroup = chart.append('g')
        .attr('class', 'hover-group');
    const verticalLine = hoverGroup.append('line')
        .attr('class', 'hover-line')
        .attr('y1', 0)
        .attr('y2', innerHeight)
        .style('opacity', 0)
        .style('stroke', '#999')
        .style('stroke-width', 1)
        .style('stroke-dasharray', '5,5');
    const pointsGroups = {};
    Object.entries(level1DiseaseData).forEach(([diseaseId, disease], i) => {
        const diseaseName = disease.name;
        const color = colorScale(i);
        const lineData = [];
        years.forEach(year => {
            const yearStr = year.toString();
            if (disease.data[yearStr]) {
                lineData.push({
                    year: year,
                    value: disease.data[yearStr].total || 0
                });
            }
        });
        if (lineData.length === 0) return;
        linesGroup.append('path')
            .datum(lineData)
            .attr('class', `line disease-${diseaseId}`)
            .attr('d', line)
            .attr('fill', 'none')
            .attr('stroke', color)
            .attr('stroke-width', 2)
            .attr('data-id', diseaseId);
        pointsGroups[diseaseId] = hoverGroup.append('g')
            .attr('class', `points-group-${diseaseId}`)
            .style('display', 'none');
        lineData.forEach(d => {
            pointsGroups[diseaseId].append('circle')
                .attr('class', `point-${d.year}`)
                .attr('cx', x(d.year))
                .attr('cy', y(d.value))
                .attr('r', 5)
                .attr('fill', color)
                .attr('stroke', '#fff')
                .attr('stroke-width', 1.5)
                .style('opacity', 0);
        });
    });
    const legend = chart.append('g')
        .attr('class', 'legend')
        .attr('transform', `translate(${innerWidth + 10}, 10)`);
    
    Object.entries(level1DiseaseData).forEach(([diseaseId, disease], i) => {
        const diseaseName = disease.name;
        const legendItem = legend.append('g')
            .attr('class', `legend-item legend-item-${diseaseId}`)
            .attr('transform', `translate(0, ${i * 25})`)
            .style('cursor', 'pointer')
            .on('mouseover', function() {
                linesGroup.selectAll('.line')
                    .style('opacity', 0.2);
                linesGroup.select(`.disease-${diseaseId}`)
                    .style('opacity', 1)
                    .style('stroke-width', 3);
            })
            .on('mouseout', function() {
                linesGroup.selectAll('.line')
                    .style('opacity', 1)
                    .style('stroke-width', 2);
            });
        
        legendItem.append('rect')
            .attr('width', 15)
            .attr('height', 15)
            .attr('fill', colorScale(i));
        
        legendItem.append('text')
            .attr('x', 20)
            .attr('y', 12)
            .text(diseaseName)
            .style('font-size', '12px');
    });
    const overlay = chart.append('rect')
        .attr('class', 'overlay')
        .attr('width', innerWidth)
        .attr('height', innerHeight)
        .style('opacity', 0)
        .style('cursor', 'crosshair')
        .on('mousemove', function(event) {
            const [mouseX] = d3.pointer(event);
            const xValue = x.invert(mouseX);
            const bisector = d3.bisector(d => d).left;
            const closestYearIndex = bisector(years, xValue);
            let year = years[closestYearIndex];
            if (closestYearIndex >= years.length) {
                year = years[years.length - 1];
            }
            else if (closestYearIndex <= 0) {
                year = years[0];
            }
            else {
                const year1 = years[closestYearIndex - 1];
                const year2 = years[closestYearIndex];
                year = (xValue - year1) < (year2 - xValue) ? year1 : year2;
            }
            verticalLine
                .attr('x1', x(year))
                .attr('x2', x(year))
                .style('opacity', 1);
            Object.keys(pointsGroups).forEach(diseaseId => {
                const points = pointsGroups[diseaseId].selectAll(`.point-${year}`);
                points.style('opacity', 1);
                pointsGroups[diseaseId].selectAll('circle:not(.point-' + year + ')')
                    .style('opacity', 0);
                pointsGroups[diseaseId].style('display', 'block');
            });
            
            let tooltipContent = `<div class="tooltip-details">Year: ${year}</div><div class="tooltip-content">`;
            
            Object.entries(level1DiseaseData).forEach(([diseaseId, disease], i) => {
                const yearData = disease.data[year];
                if (yearData) {
                    const value = yearData.total || 0;
                    const color = colorScale(i);
                    tooltipContent += `<div class="tooltip-row">
                        <span class="tooltip-color-dot" style="background-color: ${color}"></span>
                        <span class="tooltip-label">${disease.name}:</span>
                        <span class="tooltip-value">${value.toFixed(2)}</span>
                    </div>`;
                }
            });
            
            tooltipContent += '</div>';
            tooltip.html(tooltipContent)
                .style('left', (event.pageX + 10) + 'px')
                .style('top', (event.pageY - 10) + 'px')
                .style('opacity', 1);
        })
        .on('mouseout', function() {
            verticalLine.style('opacity', 0);
            Object.values(pointsGroups).forEach(group => {
                group.style('display', 'none');
                group.selectAll('circle').style('opacity', 0);
            });
            tooltip.style('opacity', 0);
        });
    overlay.on('click', function(event) {
        const [mouseX] = d3.pointer(event);
        const xValue = x.invert(mouseX);
        const bisector = d3.bisector(d => d).left;
        const closestYearIndex = bisector(years, xValue);
        let year = years[closestYearIndex];
        if (closestYearIndex >= years.length) {
            year = years[years.length - 1];
        } else if (closestYearIndex <= 0) {
            year = years[0];
        } else {
            const year1 = years[closestYearIndex - 1];
            const year2 = years[closestYearIndex];
            year = (xValue - year1) < (year2 - xValue) ? year1 : year2;
        }
        let closestDiseaseId = null;
        let minDistance = Infinity;
        Object.entries(level1DiseaseData).forEach(([diseaseId, disease]) => {
            const yearStr = year.toString();
            if (disease.data[yearStr]) {
                const value = disease.data[yearStr].total || 0;
                const yPos = y(value);
                const distance = Math.abs(d3.pointer(event)[1] - yPos);
                
                if (distance < minDistance) {
                    minDistance = distance;
                    closestDiseaseId = diseaseId;
                }
            }
        });
        if (closestDiseaseId) {
            const selectedDiseasesParam = Array.from(selectedDiseases).join(',');
            const selectedSexesParam = Array.from(selectedSexes).join(',');
            const url = `/disease_drilldown/${locationId}/${year}/${closestDiseaseId}?diseases=${selectedDiseasesParam}&sexes=${selectedSexesParam}`;
            window.location.href = url;
        }
    });
}

function setupBackButton() {
    d3.select('#back-to-map').on('click', function() {
        const selectedDiseasesParam = Array.from(selectedDiseases).join(',');
        const selectedSexesParam = Array.from(selectedSexes).join(',');
        const url = `/?diseases=${selectedDiseasesParam}&sexes=${selectedSexesParam}`;
        window.location.href = url;
    });
}
function createSunburstChart(year) {
    d3.select('#sunburst-container')
        .style('display', 'block')
        .html('<div class="loading-message">Loading disease hierarchy data...</div>');
    
    const locationId = window.location.pathname.split('/').pop();
    const diseaseParam = Array.from(selectedDiseases).join(',');
    const sexParam = Array.from(selectedSexes).join(',');
    
    d3.json(`/api/hierarchical-disease-data?year=${year}&location=${locationId}&diseases=${diseaseParam}&sexes=${sexParam}`)
        .then(data => {
            if (!data || data.error) {
                d3.select('#sunburst-container')
                    .html(`<div class="error-message">Error loading data: ${data.error || 'Unknown error'}</div>`);
                return;
            }
            
            if (data.length === 0) {
                d3.select('#sunburst-container')
                    .html('<div class="no-data-message">No data available for this selection.</div>');
                return;
            }
            d3.select('#sunburst-container').html('');
            d3.select('#sunburst-container').append('h3')
                .attr('id', 'sunburst-title')
                .text(`Disease Hierarchy Visualization for ${year}`);
            d3.select('#sunburst-container').append('div')
                .attr('id', 'sunburst-chart');

            const ids = data.map(d => d.id);
            const labels = data.map(d => d.name);
            const parents = data.map(d => d.parent);
            const values = data.map(d => d.value);
            
            const layout = {
                height: 600,
                margin: {l: 0, r: 0, b: 0, t: 50}
            };
            
            const sunburstData = [{
                type: 'sunburst',
                ids: ids,
                labels: labels,
                parents: parents,
                values: values,
                branchvalues: 'total',
                hovertemplate: '<b>%{label}</b><br>Rate: %{value:.2f}<extra></extra>',
                textinfo: 'label+value',
                texttemplate: '%{label}<br>%{value:.2f}'
            }];
            
            Plotly.newPlot('sunburst-chart', sunburstData, layout);
            
            document.getElementById('sunburst-container').scrollIntoView({
                behavior: 'smooth',
                block: 'start'
            });
        })
        .catch(error => {
            console.error('Error fetching hierarchical data:', error);
            d3.select('#sunburst-container')
                .html(`<div class="error-message">Error loading data: ${error.message}</div>`);
        });
}
