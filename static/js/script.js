document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const datasetId = document.getElementById('uploadForm').dataset.datasetId;
    const response = await fetch(`/api/dataset/${datasetId}`, {
        method: 'PUT',
        body: formData
    });
    const result = await response.json();
    if (response.ok) {
        window.location.reload();
    } else {
        alert(result.error);
    }
});