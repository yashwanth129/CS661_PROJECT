let diseaseHierarchy = {};
let locationData = {};
let selectedDiseases = new Set();
let selectedSexes = new Set([1, 2]);
let drilldownPath = [];
let currentYear = initialYear;
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
        d3.json('/api/locations')
    ]).then(([diseases, locations]) => {
        diseaseHierarchy = diseases;
        locationData = locations;
        initializeSexFilter();
        initializeDiseaseTree();
        setupNavigationButtons();
        
        drilldownPath = [{
            id: initialDiseaseId,
            name: diseaseName
        }];
        
        loadDrilldownData(initialDiseaseId);
    }).catch(error => console.error('Error loading data:', error));
});

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
        const currentDiseaseId = drilldownPath[drilldownPath.length - 1].id;
        loadDrilldownData(currentDiseaseId);
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

function loadDrilldownData(diseaseId) {
    const chartContainer = d3.select('#chart-container');
    chartContainer.html('<div class="loading-message">Loading data...</div>');
    d3.select('#details-container').style('display', 'none');
    updateBreadcrumb();
    updateBackButton();
    updateChartTitle();
    const sexParams = Array.from(selectedSexes).join(',');
    const url = `/api/disease_children?parent_id=${diseaseId}&year=${currentYear}&location_id=${locationId}&sexes=${sexParams}`;
    
    d3.json(url)
        .then(data => {
            if (data.length === 0) {
                loadDiseaseDetails(diseaseId);
            } else {
                createBarChart(data);
            }
        })
        .catch(error => {
            console.error('Error loading drilldown data:', error);
            chartContainer.html('<div class="error-message">Error loading data. Please try again.</div>');
        });
}

function createBarChart(data) {
    const container = d3.select('#chart-container');
    container.html('');
    if (data.every(d => d.value === 0)) {
        container.html('<div class="empty-data-message">No data available for the selected diseases and sexes.</div>');
        return;
    }
    
    const width = container.node().offsetWidth;
    const height = Math.max(400, data.length * 40); // Adjust height based on number of items
    const margin = { top: 20, right: 120, bottom: 50, left: 230 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    const svg = container.append('svg')
        .attr('width', width)
        .attr('height', height);
    const chart = svg.append('g')
        .attr('transform', `translate(${margin.left},${margin.top})`);
    const x = d3.scaleLinear()
        .domain([0, d3.max(data, d => d.value) * 1.1]) // Add 10% padding
        .range([0, innerWidth]);
    const y = d3.scaleBand()
        .domain(data.map(d => d.name))
        .range([0, innerHeight])
        .padding(0.2);
    const xAxis = d3.axisBottom(x)
        .ticks(5)
        .tickFormat(d => d.toFixed(1));
    const yAxis = d3.axisLeft(y)
        .tickSize(0);
    chart.append('g')
        .attr('class', 'x-axis')
        .attr('transform', `translate(0,${innerHeight})`)
        .call(xAxis);
    chart.append('g')
        .attr('class', 'y-axis')
        .call(yAxis)
        .selectAll('text')
        .attr('font-size', '12px');
    chart.append('text')
        .attr('class', 'x-axis-label')
        .attr('x', innerWidth / 2)
        .attr('y', innerHeight + 40)
        .attr('text-anchor', 'middle')
        .text('Rate per 100,000');
    const bars = chart.selectAll('.bar')
        .data(data.filter(d => d.value > 0))
        .enter()
        .append('rect')
        .attr('class', 'bar')
        .attr('x', 0)
        .attr('y', d => y(d.name))
        .attr('width', d => x(d.value))
        .attr('height', y.bandwidth())
        .attr('fill', (d, i) => colorScale(i))
        .attr('data-id', d => d.id)
        .style('cursor', 'pointer')
        .on('click', function(event, d) {
            chart.selectAll('.bar').classed('selected-bar', false);
            d3.select(this).classed('selected-bar', true);
            loadDiseaseDetails(d.id, true); // true = keep chart visible
        });
    chart.selectAll('.bar-label')
        .data(data.filter(d => d.value > 0))
        .enter()
        .append('text')
        .attr('class', 'bar-label')
        .attr('x', d => x(d.value) + 5)
        .attr('y', d => y(d.name) + y.bandwidth() / 2 + 4)
        .text(d => d.value.toFixed(2));

    chart.selectAll('.drill-indicator')
        .data(data.filter(d => d.value > 0 && d.has_children))
        .enter()
        .append('text')
        .attr('class', 'drill-indicator')
        .attr('x', d => x(d.value) + 45)
        .attr('y', d => y(d.name) + y.bandwidth() / 2 + 4)
        .attr('fill', '#666')
        .text('➤') 
        .style('cursor', 'pointer')
        .on('click', function(event, d) {
            event.stopPropagation(); 
            drilldownPath.push({
                id: d.id,
                name: d.name
            });
            loadDrilldownData(d.id);
        });
}

function loadDiseaseDetails(diseaseId, keepChart = false) {
    if (!keepChart) {
        d3.select('#chart-container').html('');
    }
    const detailsContainer = d3.select('#details-container');
    detailsContainer.style('display', 'block')
        .html('<div class="loading-message">Loading disease details...</div>');
    
    const sexParams = Array.from(selectedSexes).join(',');
    const url = `/api/disease_details?disease_id=${diseaseId}&year=${currentYear}&location_id=${locationId}&sexes=${sexParams}`;
    
    d3.json(url)
        .then(data => {
            if (data.error) {
                detailsContainer.html(`<div class="error-message">${data.error}</div>`);
                return;
            }
            const detailsHtml = `
                <div class="disease-details">
                    <div class="details-header">
                        <h3>${data.name} (${data.cause_code || 'No code'})</h3>
                        <button class="close-details">×</button>
                    </div>
                    
                    <div class="details-section">
                        <h4>Disease Information</h4>
                        <p><strong>Country:</strong> ${data.country_name}</p>
                        <p><strong>Year:</strong> ${data.year}</p>
                        <p><strong>Disease ID:</strong> ${data.id}</p>
                        <p><strong>Disease Code:</strong> ${data.cause_code || 'Not available'}</p>
                    </div>
                    
                    <div class="details-section">
                        <h4>Rate Statistics</h4>
                        <p><strong>Total Rate:</strong> ${data.rates.total.toFixed(2)} per 100,000</p>
                        ${selectedSexes.has(1) ? `<p><strong>Male Rate:</strong> ${data.rates['1'].toFixed(2)} per 100,000</p>` : ''}
                        ${selectedSexes.has(2) ? `<p><strong>Female Rate:</strong> ${data.rates['2'].toFixed(2)} per 100,000</p>` : ''}
                    </div>
                    
                    ${!data.has_children ? `
                    <div class="details-section">
                        <p>This disease has no further subcategories in the hierarchy.</p>
                    </div>
                    ` : ''}
                </div>
            `;
            
            detailsContainer.html(detailsHtml);
            detailsContainer.select('.close-details').on('click', function() {
                detailsContainer.style('display', 'none');
                d3.selectAll('.bar').classed('selected-bar', false);
            });
        })
        .catch(error => {
            console.error('Error loading disease details:', error);
            detailsContainer.html('<div class="error-message">Error loading disease details. Please try again.</div>');
        });
}

function updateBreadcrumb() {
    const breadcrumbContainer = d3.select('#breadcrumb-container');
    breadcrumbContainer.html('');
    
    drilldownPath.forEach((item, index) => {
        if (index > 0) {
            breadcrumbContainer.append('span')
                .attr('class', 'breadcrumb-separator')
                .text(' > ');
        }
        
        const breadcrumbItem = breadcrumbContainer.append('span')
            .attr('class', index < drilldownPath.length - 1 ? 'breadcrumb-item clickable' : 'breadcrumb-item')
            .text(item.name);
        if (index < drilldownPath.length - 1) {
            breadcrumbItem.on('click', function() {
                drilldownPath = drilldownPath.slice(0, index + 1);
                loadDrilldownData(item.id);
            });
        }
    });
}

function updateChartTitle() {
    const currentDisease = drilldownPath[drilldownPath.length - 1];
    d3.select('#chart-title').text(`${currentDisease.name} Breakdown (${currentYear})`);
}
function updateBackButton() {
    const backContainer = d3.select('#back-container');
    const backButton = d3.select('#back-to-parent');
    
    if (drilldownPath.length > 1) {
        backContainer.style('display', 'block');
        backButton.on('click', function() {
            drilldownPath.pop();
            const parentDisease = drilldownPath[drilldownPath.length - 1];
            loadDrilldownData(parentDisease.id);
        });
    } else {
        backContainer.style('display', 'none');
    }
}
function setupNavigationButtons() {
    d3.select('#back-to-country').on('click', function() {
        const diseasesParam = Array.from(selectedDiseases).join(',');
        const sexesParam = Array.from(selectedSexes).join(',');
        window.location.href = `/country/${locationId}?diseases=${diseasesParam}&sexes=${sexesParam}`;
    });
    
    d3.select('#back-to-map').on('click', function() {
        const diseasesParam = Array.from(selectedDiseases).join(',');
        const sexesParam = Array.from(selectedSexes).join(',');
        window.location.href = `/?diseases=${diseasesParam}&sexes=${sexesParam}`;
    });
}
