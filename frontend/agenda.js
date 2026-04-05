// Configuração da API
const API_URL = 'https://agenda-de-atendimento.onrender.com';

// Estado da aplicação
const state = {
    selectedDate: null,
    selectedTime: null,
    availableDays: [],
    availableSlots: [],
};

// Elementos do DOM
const elements = {
    calendarGroups: document.getElementById('calendar-groups'),
    calendarContext: document.getElementById('calendar-context'),
    calendarLoading: document.getElementById('calendar-loading'),
    timeGrid: document.getElementById('time-grid'),
    timeLoading: document.getElementById('time-loading'),
    stepDate: document.getElementById('step-date'),
    stepTime: document.getElementById('step-time'),
    stepInfo: document.getElementById('step-info'),
    stepConfirm: document.getElementById('step-confirm'),
    form: document.getElementById('booking-form'),
    btnConfirm: document.getElementById('btn-confirm'),
    alertContainer: document.getElementById('alert-container'),

    nome: document.getElementById('nome'),
    email: document.getElementById('email'),
    telefone: document.getElementById('telefone'),
    mensagem: document.getElementById('mensagem'),

    summaryDate: document.getElementById('summary-date'),
    summaryTime: document.getElementById('summary-time'),
    summaryName: document.getElementById('summary-name'),
    summaryEmail: document.getElementById('summary-email'),
    summaryPhone: document.getElementById('summary-phone'),
    summaryType: document.getElementById('summary-type')
};

function formatDate(dateString) {
    const date = new Date(dateString + 'T00:00:00');
    return date.toLocaleDateString('pt-BR', {
        day: '2-digit',
        month: 'long',
        year: 'numeric'
    });
}

function getWeekday(dateString) {
    const date = new Date(dateString + 'T00:00:00');
    const weekdays = ['Dom', 'Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb'];
    return weekdays[date.getDay()];
}

function getMonthYear(dateString) {
    const date = new Date(dateString + 'T00:00:00');
    const month = date.toLocaleDateString('pt-BR', { month: 'long' });
    const year = date.getFullYear();
    return `${month} de ${year}`;
}

function capitalizeMonthLabel(label) {
    return label.charAt(0).toUpperCase() + label.slice(1);
}

function updateCalendarContext() {
    if (!state.availableDays.length) {
        elements.calendarContext.classList.add('hidden');
        elements.calendarContext.textContent = '';
        return;
    }

    const uniqueMonths = [...new Set(state.availableDays.map(day => getMonthYear(day.data)))];

    if (uniqueMonths.length === 1) {
        elements.calendarContext.textContent = `Disponibilidade de ${capitalizeMonthLabel(uniqueMonths[0])}`;
    } else {
        const firstMonth = capitalizeMonthLabel(uniqueMonths[0]);
        const lastMonth = capitalizeMonthLabel(uniqueMonths[uniqueMonths.length - 1]);
        elements.calendarContext.textContent = `Disponibilidade entre ${firstMonth} e ${lastMonth}`;
    }

    elements.calendarContext.classList.remove('hidden');
}

function getSelectedType() {
    const checked = document.querySelector('input[name="tipo"]:checked');
    return checked ? checked.value : 'online';
}

function syncTypeSelection() {
    document.querySelectorAll('.type-option').forEach(option => {
        const radio = option.querySelector('input[type="radio"]');
        option.classList.toggle('selected', radio.checked);
    });
}

function showAlert(message, type = 'success') {
    const alertClass = type === 'success' ? 'alert-success' : 'alert-error';
    elements.alertContainer.innerHTML = `<div class="alert ${alertClass}">${message}</div>`;

    setTimeout(() => {
        elements.alertContainer.innerHTML = '';
    }, 6000);
}

function activateStep(step) {
    document.querySelectorAll('.step').forEach(s => s.classList.remove('active'));
    step.classList.add('active');
}

async function fetchAvailableDays() {
    try {
        elements.calendarLoading.classList.remove('hidden');
        elements.calendarGroups.innerHTML = '';

        const response = await fetch(`${API_URL}/proximos-dias/21`);
        if (!response.ok) throw new Error('Erro ao carregar dias disponíveis.');

        const data = await response.json();
        state.availableDays = data.dias;
        renderCalendar();
    } catch (error) {
        console.error('Erro:', error);
        showAlert('Não foi possível carregar as datas disponíveis agora. Tente novamente em instantes.', 'error');
    } finally {
        elements.calendarLoading.classList.add('hidden');
    }
}

async function fetchAvailableSlots(date) {
    try {
        elements.timeLoading.classList.remove('hidden');
        elements.timeGrid.innerHTML = '';

        const response = await fetch(`${API_URL}/disponibilidade/${date}`);
        if (!response.ok) throw new Error('Erro ao carregar horários.');

        const data = await response.json();
        state.availableSlots = data.slots;
        renderTimeSlots();
    } catch (error) {
        console.error('Erro:', error);
        showAlert('Não foi possível carregar os horários para esta data. Tente novamente.', 'error');
    } finally {
        elements.timeLoading.classList.add('hidden');
    }
}

async function submitBooking() {
    try {
        elements.btnConfirm.disabled = true;
        elements.btnConfirm.textContent = 'Enviando solicitação...';

        const bookingData = {
            nome: elements.nome.value.trim(),
            email: elements.email.value.trim(),
            telefone: elements.telefone.value.trim(),
            data: state.selectedDate,
            horario: state.selectedTime,
            tipo_atendimento: getSelectedType(),
            mensagem: elements.mensagem.value.trim()
        };

        const response = await fetch(`${API_URL}/agendar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(bookingData)
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || 'Erro ao registrar o agendamento.');
        }

        showAlert('✅ Solicitação enviada com sucesso. O horário foi registrado e poderá ser confirmado em seguida.', 'success');

        setTimeout(() => {
            resetForm();
        }, 3200);
    } catch (error) {
        console.error('Erro:', error);
        showAlert(error.message || 'Não foi possível concluir a solicitação. Tente novamente.', 'error');
    } finally {
        elements.btnConfirm.disabled = false;
        elements.btnConfirm.textContent = 'Confirmar solicitação de agendamento';
    }
}

function renderCalendar() {
    elements.calendarGroups.innerHTML = '';
    updateCalendarContext();

    const groupedByMonth = state.availableDays.reduce((groups, day) => {
        const monthKey = getMonthYear(day.data);
        if (!groups[monthKey]) {
            groups[monthKey] = [];
        }
        groups[monthKey].push(day);
        return groups;
    }, {});

    const monthEntries = Object.entries(groupedByMonth);
    const showInternalMonthLabel = monthEntries.length > 1;

    monthEntries.forEach(([monthLabel, days]) => {
        const monthBlock = document.createElement('div');
        monthBlock.className = 'calendar-month-block';

        if (showInternalMonthLabel) {
            const monthTitle = document.createElement('div');
            monthTitle.className = 'calendar-month-label';
            monthTitle.textContent = capitalizeMonthLabel(monthLabel);
            monthBlock.appendChild(monthTitle);
        }

        const daysGrid = document.createElement('div');
        daysGrid.className = 'calendar-month-days';

        days.forEach(day => {
            const dayButton = document.createElement('button');
            dayButton.className = 'day-button';
            dayButton.type = 'button';

            const date = new Date(day.data + 'T00:00:00');
            const dayNumber = date.getDate();
            const weekday = getWeekday(day.data);

            dayButton.innerHTML = `
                <span class="day-date">${dayNumber}</span>
                <span class="day-weekday">${weekday}</span>
            `;

            dayButton.addEventListener('click', () => selectDate(day.data, dayButton));
            daysGrid.appendChild(dayButton);
        });

        monthBlock.appendChild(daysGrid);
        elements.calendarGroups.appendChild(monthBlock);
    });
}

function renderTimeSlots() {
    elements.timeGrid.innerHTML = '';

    if (state.availableSlots.length === 0) {
        elements.timeGrid.innerHTML = '<p class="empty-state">Nenhum horário disponível para esta data. Escolha outro dia para continuar.</p>';
        return;
    }

    state.availableSlots.forEach(slot => {
        const timeButton = document.createElement('button');
        timeButton.className = 'time-button';
        timeButton.type = 'button';
        timeButton.textContent = slot.horario;
        timeButton.disabled = !slot.disponivel;

        if (slot.disponivel) {
            timeButton.addEventListener('click', () => selectTime(slot.horario, timeButton));
        }

        elements.timeGrid.appendChild(timeButton);
    });
}

function selectDate(date, button) {
    state.selectedDate = date;
    state.selectedTime = null;

    document.querySelectorAll('.day-button').forEach(btn => btn.classList.remove('selected'));
    document.querySelectorAll('.time-button').forEach(btn => btn.classList.remove('selected'));
    button.classList.add('selected');

    updateSummary();
    activateStep(elements.stepTime);
    fetchAvailableSlots(date);
}

function selectTime(time, button) {
    state.selectedTime = time;

    document.querySelectorAll('.time-button').forEach(btn => btn.classList.remove('selected'));
    button.classList.add('selected');

    updateSummary();
    activateStep(elements.stepInfo);
}

function updateSummary() {
    elements.summaryDate.textContent = state.selectedDate ? formatDate(state.selectedDate) : '-';
    elements.summaryTime.textContent = state.selectedTime || '-';
    elements.summaryName.textContent = elements.nome.value || '-';
    elements.summaryEmail.textContent = elements.email.value || '-';
    elements.summaryPhone.textContent = elements.telefone.value || '-';

    const tipoSelecionado = getSelectedType();
    elements.summaryType.textContent = tipoSelecionado === 'online' ? '🌐 Online' : '📍 Presencial';
}

function resetForm() {
    state.selectedDate = null;
    state.selectedTime = null;
    state.availableSlots = [];

    elements.form.reset();
    document.querySelector('#type-online input[type="radio"]').checked = true;
    syncTypeSelection();

    document.querySelectorAll('.day-button').forEach(btn => btn.classList.remove('selected'));
    document.querySelectorAll('.time-button').forEach(btn => btn.classList.remove('selected'));

    elements.timeGrid.innerHTML = '<p class="empty-state">Escolha primeiro uma data para visualizar os horários disponíveis.</p>';

    elements.stepTime.classList.remove('active');
    elements.stepInfo.classList.remove('active');
    elements.stepConfirm.classList.remove('active');
    elements.stepDate.classList.add('active');

    updateSummary();
    fetchAvailableDays();
}

document.querySelectorAll('.type-option').forEach(option => {
    option.addEventListener('click', function () {
        const radio = this.querySelector('input[type="radio"]');
        radio.checked = true;
        syncTypeSelection();
        updateSummary();
    });
});

elements.form.addEventListener('submit', (e) => {
    e.preventDefault();
});

[elements.nome, elements.email, elements.telefone, elements.mensagem].forEach(input => {
    input.addEventListener('input', () => {
        updateSummary();

        if (elements.form.checkValidity() && state.selectedDate && state.selectedTime) {
            activateStep(elements.stepConfirm);
        }
    });

    input.addEventListener('blur', () => {
        updateSummary();

        if (elements.form.checkValidity() && state.selectedDate && state.selectedTime) {
            activateStep(elements.stepConfirm);
        }
    });
});

elements.btnConfirm.addEventListener('click', () => {
    if (!state.selectedDate || !state.selectedTime) {
        showAlert('Selecione uma data e um horário antes de confirmar a solicitação.', 'error');
        activateStep(state.selectedDate ? elements.stepTime : elements.stepDate);
        return;
    }

    if (!elements.form.checkValidity()) {
        showAlert('Preencha os campos obrigatórios antes de concluir o envio.', 'error');
        activateStep(elements.stepInfo);
        elements.form.reportValidity();
        return;
    }

    updateSummary();
    submitBooking();
});

elements.telefone.addEventListener('input', (e) => {
    let value = e.target.value.replace(/\D/g, '');
    if (value.length > 11) value = value.substring(0, 11);

    if (value.length > 6) {
        value = `(${value.substring(0, 2)}) ${value.substring(2, 7)}-${value.substring(7)}`;
    } else if (value.length > 2) {
        value = `(${value.substring(0, 2)}) ${value.substring(2)}`;
    }

    e.target.value = value;
    updateSummary();
});

document.addEventListener('DOMContentLoaded', () => {
    syncTypeSelection();
    updateSummary();
    fetchAvailableDays();
});
