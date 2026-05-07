// static/js/main.js

$(document).ready(function() {
    // Sidebar location search
    $('#searchLocations').on('keyup', function() {
        var value = $(this).val().toLowerCase();
        $('.sidebar .nav-link').filter(function() {
            $(this).toggle($(this).text().toLowerCase().indexOf(value) > -1);
        });
    });

    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        $('.alert').alert('close');
    }, 5000);

    // Tooltip initialization
    $('[data-bs-toggle="tooltip"]').tooltip();

    // Smooth scroll for anchor links
    $('a[href^="#"]').on('click', function(event) {
        if (this.hash !== "") {
            event.preventDefault();
            var hash = this.hash;
            $('html, body').animate({
                scrollTop: $(hash).offset().top - 70
            }, 800);
        }
    });

    // Copy to clipboard for code examples
    $('pre').each(function() {
        $(this).append('<button class="btn btn-sm btn-outline-secondary copy-btn" style="position: absolute; right: 10px; top: 10px;">Copy</button>');
    });

    $('.copy-btn').click(function() {
        var code = $(this).siblings('code').text();
        navigator.clipboard.writeText(code).then(function() {
            var originalText = $(this).text();
            $(this).text('Copied!');
            setTimeout(function() {
                $(this).text(originalText);
            }.bind(this), 2000);
        }.bind(this));
    });

    // Form validation enhancement
    $('form').submit(function() {
        $(this).find(':submit').prop('disabled', true).html('<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Processing...');
    });

    // Dynamic table sorting
    $('table th.sortable').click(function() {
        var table = $(this).parents('table').eq(0);
        var rows = table.find('tr:gt(0)').toArray().sort(comparer($(this).index()));
        this.asc = !this.asc;
        if (!this.asc) {
            rows = rows.reverse();
        }
        for (var i = 0; i < rows.length; i++) {
            table.append(rows[i]);
        }
        $(this).toggleClass('sorted-asc sorted-desc');
    });

    function comparer(index) {
        return function(a, b) {
            var valA = getCellValue(a, index), valB = getCellValue(b, index);
            return $.isNumeric(valA) && $.isNumeric(valB) ? valA - valB : valA.toString().localeCompare(valB);
        };
    }

    function getCellValue(row, index) {
        return $(row).children('td').eq(index).text();
    }

    // Chart color theme
    Chart.defaults.color = '#6c757d';
    Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";

    // Initialize all charts on page
    initializeCharts();

    // Dark/Light mode toggle (optional)
    $('#themeToggle').click(function() {
        $('body').toggleClass('dark-mode');
        $(this).find('i').toggleClass('fa-moon fa-sun');
        localStorage.setItem('theme', $('body').hasClass('dark-mode') ? 'dark' : 'light');
    });

    // Check for saved theme preference
    if (localStorage.getItem('theme') === 'dark') {
        $('body').addClass('dark-mode');
        $('#themeToggle i').removeClass('fa-moon').addClass('fa-sun');
    }
});

function initializeCharts() {
    // This function can be extended to initialize specific charts
    // Currently handled by individual template scripts
}

// API Helper Functions
const API = {
    baseUrl: window.location.origin + '/api/v1/',

    async getLocations(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseUrl}locations/?${queryString}`);
        return await response.json();
    },

    async getClimateData(locationId, startDate, endDate) {
        const params = {
            location_id: locationId,
            start_date: startDate,
            end_date: endDate
        };
        const queryString = new URLSearchParams(params).toString();
        const response = await fetch(`${this.baseUrl}climate-data/?${queryString}`);
        return await response.json();
    },

    async performSolarAnalysis(data) {
        const response = await fetch(`${this.baseUrl}solar-analysis/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(data)
        });
        return await response.json();
    },

    async exportData(format = 'csv', params = {}) {
        const queryString = new URLSearchParams(params).toString();
        window.open(`${this.baseUrl}export/climate-data/${format}/?${queryString}`, '_blank');
    }
};

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = API;
} else {
    window.ShamsiSmartAPI = API;
}