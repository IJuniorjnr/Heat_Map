const ip = "localhost";
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
    const maxTime = 7200; // 2 horas (7200 segundos)
    const minTime = 0;
    if (tempo > maxTime) tempo = maxTime;
    if (tempo < minTime) tempo = minTime;

    let r, g, b;
    if (tempo >= 0) {
        if (tempo > 3600) {
            const greenToYellowRatio = (tempo - 3600) / 3600;
            r = 255 - Math.floor(255 * greenToYellowRatio);
            g = 255;
            b = 0;
        } else {
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
    timerElement.style.color = timer.tempo < 0 ? '#ffffff' : '#000000';
    return timerElement;
};

const updateTimerElement = (timer) => {
    const timerElement = document.getElementById(`timer-${timer.actual_arrival_destination}`);
    if (timerElement) {
        timerElement.querySelector('p').textContent = formatTime(timer.tempo);
        timerElement.style.backgroundColor = getBackgroundColor(timer.tempo);
        timerElement.style.color = timer.tempo < 0 ? '#ffffff' : '#000000';
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

const fetchTimers = async (prefix) => {
    try {
        const response = await fetch(`http://${ip}:5000/api/timers/${prefix}`);
        if (!response.ok) throw new Error('Network response was not ok');
        let timers = await response.json();
        const container = document.getElementById('timers-container');
        container.innerHTML = '';
        timers.forEach(timer => {
            const timerElement = createTimerElement(timer);
            container.appendChild(timerElement);
        });
        socket.on(`timerUpdate-${prefix}`, (updatedTimer) => {
            updateTimerElement(updatedTimer);
        });
    } catch (error) {
        console.error('Error fetching timers:', error);
    }
};

const fetchLastUpdate = async () => {
    try {
        const response = await fetch(`http://${ip}:5000/api/last-update`);
        if (!response.ok) throw new Error('Network response was not ok');
        const data = await response.json();
        document.getElementById('last-updated').textContent = `Última atualização: ${new Date(data.last_updated).toLocaleString()}`;
    } catch (error) {
        console.error('Error fetching last update:', error);
    }
};

const fetchProductionData = async (prefix) => {
    try {
        const response = await fetch(`http://${ip}:5000/api/production-data`);
        if (!response.ok) throw new Error('Network response was not ok');
        const data = await response.json();
        renderProductionData(data, prefix);
    } catch (error) {
        console.error('Error fetching production data:', error);
    }
};

const renderProductionData = (data, prefix) => {
    const container = document.getElementById('production-data-container');
    container.innerHTML = ''; // Limpa os dados de produção atuais

    const relevantData = data.filter(item => item.device_code.endsWith(prefix));

    if (relevantData.length === 0) {
        container.innerHTML = '<p>Nenhum dado de produção disponível para este código de dispositivo.</p>';
        return;
    }

    const deviceCode = relevantData[0].device_code;
    const deviceElement = document.createElement('div');
    deviceElement.className = 'device-data';

    const totalProduced = relevantData.reduce((sum, item) => sum + item.total_produced_by_user, 0);
    deviceElement.innerHTML = `<h3>${deviceCode} - Total Produzido: ${totalProduced}</h3>`;

    const userList = document.createElement('ul');
    relevantData.forEach(item => {
        const userItem = document.createElement('li');
        userItem.textContent = `${item.operator}: ${item.total_produced_by_user}`;
        userList.appendChild(userItem);
    });

    deviceElement.appendChild(userList);
    container.appendChild(deviceElement);
};

document.addEventListener('DOMContentLoaded', () => {
    const prefix = window.location.pathname.replace('/', '').toUpperCase();
    fetchTimers(prefix);
    fetchLastUpdate();
    fetchProductionData(prefix);

    socket.on('lastUpdate', (lastUpdated) => {
        document.getElementById('last-updated').textContent = `Última atualização: ${new Date(lastUpdated).toLocaleString()}`;
    });
});
