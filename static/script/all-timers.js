ip = "10.41.202.130"
const socket = io(`http://${ip}:5000`);

const formatTime = (seconds) => {
    const absSeconds = Math.abs(seconds);
    const h = Math.floor(absSeconds / 3600).toString().padStart(2, '0');
    const m = Math.floor((absSeconds % 3600) / 60).toString().padStart(2, '0');
    const s = (absSeconds % 60).toString().padStart(2, '0');
    return seconds < 0 ? `-${h}:${m}:${s}` : `${h}:${m}:${s}`;
};

const getBackgroundColor = (tempo) => {
    if (tempo < 0) {
        return 'black';
    }
    const maxTime = 7200;
    const minTime = 0;
    if (tempo > maxTime) tempo = maxTime;
    if (tempo < minTime) tempo = minTime;

    let r, g, b;
    if (tempo >= 0) {
        // Green to yellow to red transition
        if (tempo > 3600) {
            // Green to yellow
            const greenToYellowRatio = (tempo - 3600) / 3600;
            r = 255 - Math.floor(255 * greenToYellowRatio);
            g = 255;
            b = 0;
        } else {
            // Yellow to red
            const yellowToRedRatio = tempo / 3600;
            r = 255;
            g = Math.floor(255 * yellowToRedRatio);
            b = 0;
        }
    }

    return `rgb(${r}, ${g}, ${b})`;
};

const createTimerElement = (timer) => {
    const timerElement = document.createElement('div');
    timerElement.className = 'timer';
    timerElement.id = `timer-${timer.actual_arrival_destination}`;
    timerElement.innerHTML = `
        <h2>${timer.actual_arrival_destination}</h2>
        <p>${formatTime(timer.tempo)}</p>
    `;
    timerElement.style.backgroundColor = getBackgroundColor(timer.tempo);
    if (timer.tempo < 0) {
        timerElement.style.color = '#ffffff';
    }
    return timerElement;
};

const updateTimerElement = (timer) => {
    const timerElement = document.getElementById(`timer-${timer.actual_arrival_destination}`);
    if (timerElement) {
        timerElement.querySelector('p').textContent = formatTime(timer.tempo);
        timerElement.style.backgroundColor = getBackgroundColor(timer.tempo);
        if (timer.tempo < 0) {
            timerElement.style.color = '#ffffff';
        } else {
            timerElement.style.color = '#000000';
        }
    } else {
        const newTimerElement = createTimerElement(timer);
        document.getElementById('timers-container').appendChild(newTimerElement);
    }
};

const removeMissingTimers = (currentTimers) => {
    const timerElements = document.querySelectorAll('.timer');
    timerElements.forEach(timerElement => {
        const timerId = timerElement.id.replace('timer-', '');
        const timerExists = currentTimers.some(timer => timer.actual_arrival_destination === timerId);
        if (!timerExists) {
            timerElement.remove();
        }
    });
};

const updateTimersCount = (count) => {
    const countElement = document.getElementById('timers-count');
    countElement.textContent = `(${count})`;
};

const renderTimers = (timers) => {
    const container = document.getElementById('timers-container');
    container.innerHTML = ''; // Clear current timers
    timers.forEach(timer => {
        const timerElement = createTimerElement(timer);
        container.appendChild(timerElement);
    });
};

const fetchTimers = async () => {
    try {
        const response = await fetch(`http://${ip}:5000/api/timers/all?t=${Date.now()}`);
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        const timers = await response.json();
        const negativeTimers = timers.filter(timer => timer.tempo < 0)
                                     .sort((a, b) => a.tempo - b.tempo);
        
        removeMissingTimers(negativeTimers);
        renderTimers(negativeTimers);
        updateTimersCount(negativeTimers.length);
    } catch (error) {
        console.error('Error fetching timers:', error);
    }
};

const fetchLastUpdate = async () => {
    try {
        const response = await fetch(`http://${ip}/api/last-update?t=${Date.now()}`);
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        const data = await response.json();
        document.getElementById('last-updated').textContent = `última atualização: ${new Date(data.last_updated).toLocaleString()}`;
    } catch (error) {
        console.error('Error fetching last update:', error);
    }
};

document.addEventListener('DOMContentLoaded', () => {
    fetchTimers();
    fetchLastUpdate();
    setInterval(fetchTimers, 5000); // Re-fetch timers every 5 seconds
    socket.on('timerUpdate', (updatedTimer) => {
        if (updatedTimer.tempo < 0) {
            fetchTimers(); // Re-fetch timers to ensure order and update
        }
    });

    // Get last update event from server
    socket.on('lastUpdate', (lastUpdated) => {
        document.getElementById('last-updated').textContent = `última atualização: ${new Date(lastUpdated).toLocaleString()}`;
    });
});