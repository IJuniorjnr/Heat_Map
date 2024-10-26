let filterStart = null;
let filterEnd = null;

const toggleDropdown = () => {
    document.getElementById('dropdown').classList.toggle('show');
};

window.onclick = function(event) {
    if (!event.target.matches('.menu')) {
        var dropdowns = document.getElementsByClassName("dropdown-content");
        for (var i = 0; i < dropdowns.length; i++) {
            var openDropdown = dropdowns[i];
            if (openDropdown.classList.contains('show')) {
                openDropdown.classList.remove('show');
            }
        }
    }
};

const filterTimers = (start, end) => {
    filterStart = start;
    filterEnd = end;
    const prefix = window.location.pathname.replace('/', '').toUpperCase();
    fetchTimers(prefix);
};

const clearFilters = () => {
    filterStart = null;
    filterEnd = null;
    const prefix = window.location.pathname.replace('/', '').toUpperCase();
    fetchTimers(prefix);
};

const applyFilters = (timers) => {
    if (filterStart !== null && filterEnd !== null) {
        return timers.filter(timer => {
            const timerSuffix = timer.actual_arrival_destination.split('-').pop();
            return timerSuffix >= filterStart && timerSuffix <= filterEnd;
        });
    }
    return timers;
};