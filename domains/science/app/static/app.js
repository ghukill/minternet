// Science Lab - JavaScript Application
// Demonstrates both working and broken patterns for web archiving

document.addEventListener('DOMContentLoaded', function() {
    loadFeatured();
    loadExperiments();
});

const publicHost = window.PUBLIC_HOST || window.location.host;
const publicScheme = window.PUBLIC_SCHEME || window.location.protocol.replace(':', '');
const baseUrl = `${publicScheme}://${publicHost}`;

// BROKEN PATTERN: Uses absolute URL - will fail in replay
function loadFeatured() {
    const container = document.getElementById('featured');

    // This absolute URL will NOT be rewritten by web archives
    // and will try to fetch from the live site during replay
    fetch(`${baseUrl}/api/featured`)
        .then(response => {
            if (!response.ok) throw new Error('Failed to load');
            return response.json();
        })
        .then(data => {
            const featured = data.featured;
            container.innerHTML = `
                <div class="flex items-start gap-4">
                    <div class="flex-1">
                        <h3 class="text-xl font-semibold text-indigo-600">${featured.title}</h3>
                        <p class="text-gray-600 mt-2">Our most popular experiment!</p>
                        <button onclick="loadExperimentDetail(${featured.id})"
                                class="mt-4 bg-indigo-600 text-white px-4 py-2 rounded hover:bg-indigo-700">
                            View Details
                        </button>
                    </div>
                </div>
                <p class="text-xs text-red-500 mt-4">
                    ⚠️ This section was loaded via absolute URL (${baseUrl}/api/featured)
                </p>
            `;
        })
        .catch(error => {
            container.innerHTML = `
                <div class="error">
                    <strong>Failed to load featured experiment</strong>
                    <p class="mt-2">This is expected in a web archive replay! The absolute URL
                    <code>${baseUrl}/api/featured</code> cannot be rewritten.</p>
                </div>
            `;
            console.error('Featured load error:', error);
        });
}

// WORKING PATTERN: Uses relative URL - should work in replay
function loadExperiments() {
    const container = document.getElementById('experiments');

    // This relative URL WILL be rewritten by web archives
    fetch('/api/experiments')
        .then(response => {
            if (!response.ok) throw new Error('Failed to load');
            return response.json();
        })
        .then(data => {
            container.innerHTML = '';

            data.experiments.forEach(exp => {
                // Dynamically creating DOM elements
                const card = document.createElement('div');
                card.className = 'bg-white rounded-lg shadow p-4 hover:shadow-lg transition-shadow';

                const badge = getBadgeClass(exp.difficulty);

                card.innerHTML = `
                    <span class="text-xs ${badge} px-2 py-1 rounded">${exp.difficulty}</span>
                    <span class="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded ml-2">${exp.category}</span>
                    <h3 class="text-lg font-semibold mt-2">${exp.title}</h3>
                    <button onclick="loadExperimentDetail(${exp.id})"
                            class="mt-3 text-indigo-600 hover:text-indigo-800 text-sm font-medium">
                        View Details →
                    </button>
                `;

                container.appendChild(card);
            });

            // Add success indicator
            const note = document.createElement('div');
            note.className = 'col-span-full text-xs text-green-600 mt-2';
            note.innerHTML = '✓ This section was loaded via relative URL (/api/experiments)';
            container.appendChild(note);
        })
        .catch(error => {
            container.innerHTML = `
                <div class="error col-span-full">
                    <strong>Failed to load experiments</strong>
                    <p class="mt-2">Error: ${error.message}</p>
                </div>
            `;
            console.error('Experiments load error:', error);
        });
}

// Load experiment detail - also uses relative URL
function loadExperimentDetail(id) {
    const modal = document.getElementById('modal');
    const content = document.getElementById('modal-content');

    modal.classList.remove('hidden');
    modal.classList.add('flex');
    content.innerHTML = '<p class="text-gray-500">Loading...</p>';

    // Relative URL - should work in replay
    fetch(`/api/experiment/${id}`)
        .then(response => {
            if (!response.ok) throw new Error('Failed to load');
            return response.json();
        })
        .then(exp => {
            const badge = getBadgeClass(exp.difficulty);

            content.innerHTML = `
                <h2 class="text-2xl font-bold text-indigo-600">${exp.title}</h2>
                <div class="mt-2">
                    <span class="text-xs ${badge} px-2 py-1 rounded">${exp.difficulty}</span>
                    <span class="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded ml-2">${exp.category}</span>
                </div>
                <p class="mt-4 text-gray-700">${exp.description}</p>
                <h3 class="mt-4 font-semibold">Materials Needed:</h3>
                <ul class="mt-2 list-disc list-inside text-gray-600">
                    ${exp.materials.map(m => `<li>${m}</li>`).join('')}
                </ul>
                <p class="text-xs text-green-600 mt-4">
                    ✓ Loaded via relative URL (/api/experiment/${id})
                </p>
            `;
        })
        .catch(error => {
            content.innerHTML = `
                <div class="error">
                    <strong>Failed to load experiment details</strong>
                    <p class="mt-2">Error: ${error.message}</p>
                </div>
            `;
        });
}

function closeModal() {
    const modal = document.getElementById('modal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

function getBadgeClass(difficulty) {
    switch(difficulty) {
        case 'Easy': return 'bg-green-100 text-green-800';
        case 'Medium': return 'bg-yellow-100 text-yellow-800';
        case 'Hard': return 'bg-red-100 text-red-800';
        default: return 'bg-gray-100 text-gray-800';
    }
}

// Close modal on escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeModal();
    }
});

// Close modal on background click
document.getElementById('modal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeModal();
    }
});
