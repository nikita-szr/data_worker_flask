document.getElementById('uploadForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const formData = new FormData(e.target);
    const response = await fetch(`/api/dataset/${{{ dataset_id }}}`, {
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