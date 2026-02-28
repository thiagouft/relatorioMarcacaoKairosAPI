document.addEventListener('DOMContentLoaded', () => {
    // Use the global window variable we set in the template
    const gruposRelogios = window.gruposRelogios || {};

    // Handle tab navigation via hash
    function handleHashChange() {
        const isDesligamento = window.location.hash === '#desligamento';
        const panelComandos = document.getElementById('panel-envio-comandos');
        const panelRelogios = document.getElementById('panel-envio-relogios');
        const panelDesligamento = document.getElementById('panel-desligamento');

        if (panelComandos) panelComandos.style.display = isDesligamento ? 'none' : 'block';
        if (panelRelogios) panelRelogios.style.display = isDesligamento ? 'none' : 'block';
        if (panelDesligamento) panelDesligamento.style.display = isDesligamento ? 'block' : 'none';
    }

    window.addEventListener('hashchange', handleHashChange);
    handleHashChange(); // Executar ao carregar a página

    // Renderiza os links de download (remove duplicados antes de inserir)
    function renderDownloads(resultDiv, result) {
        // remove se já existir
        const existing = resultDiv.querySelectorAll('.download-section');
        existing.forEach((el) => el.remove());

        const parts = [];
        if (result.sucessoFileName) {
            parts.push(`<a href="/static/${result.sucessoFileName}" target="_blank">📥 Baixar Arquivo de Sucesso</a>`);
        }
        if (result.falhaFileName) {
            parts.push(`<a href="/static/${result.falhaFileName}" target="_blank">📥 Baixar Arquivo de Falhas</a>`);
        }
        if (result.logFileName) {
            parts.push(`<a href="/static/${result.logFileName}" target="_blank">📥 Baixar Log de Falhas</a>`);
        }
        if (parts.length === 0) return;

        const div = document.createElement('div');
        div.className = 'download-section';
        div.innerHTML = '<strong>Arquivos Gerados:</strong>' + parts.join('');
        resultDiv.appendChild(div);
    }

    document.getElementById("uploadForm").addEventListener("submit", async (e) => {
        e.preventDefault();

        const fileInput = document.getElementById("arquivo");
        const matriculasInput = document.getElementById("matriculas").value.trim();
        const resultDiv = document.getElementById("result");

        resultDiv.innerHTML = ""; // Limpa os antigos resultados
        resultDiv.style.display = "none";

        const formData = new FormData();
        if (fileInput.files.length > 0) {
            formData.append("arquivo", fileInput.files[0]);
        } else if (matriculasInput.length > 0) {
            const matriculas = matriculasInput
                .split(",")
                .map((m) => m.trim())
                .filter((m) => m !== "");

            if (matriculas.length === 0) {
                alert("Por favor, digite pelo menos uma matrícula válida!");
                return;
            }
            formData.append("matriculas", JSON.stringify(matriculas));
        } else {
            alert("Por favor, selecione um arquivo ou digite as matrículas!");
            return;
        }

        const comandos = {};
        const checkboxesComandos = document.querySelectorAll('input[name="comandos"]:checked');
        if (checkboxesComandos.length === 0) {
            alert("Por favor, selecione pelo menos um comando!");
            return;
        }
        checkboxesComandos.forEach((checkbox) => {
            comandos[checkbox.value] = true;
        });

        const relogios = [];
        const checkboxesRelogios = document.querySelectorAll('input[name="relogios"]:checked');
        if (checkboxesRelogios.length === 0) {
            alert("Por favor, selecione pelo menos um relógio!");
            return;
        }
        checkboxesRelogios.forEach((checkbox) => {
            relogios.push(parseInt(checkbox.value, 10));
        });

        formData.append("comandos", JSON.stringify(comandos));
        formData.append("relogios", JSON.stringify(relogios));

        const progressBar = document.getElementById("progressBar");
        const progressBarInner = progressBar.querySelector(".progress-bar-fill");
        progressBar.style.display = "block";
        progressBarInner.textContent = "Processando...";
        progressBarInner.style.backgroundColor = "#ecc94b"; // yellow while processing

        try {
            const response = await fetch("/api/envio_comando/processar", {
                method: "POST",
                body: formData,
            });

            let result;
            try {
                result = await response.json();
            } catch (e) {
                throw new Error("Resposta do servidor não pôde ser interpretada.");
            }

            if (!response.ok) {
                throw new Error(result.mensagem || "Erro ao processar a requisição no servidor.");
            }

            progressBar.style.display = "none";
            resultDiv.style.display = "block";

            if (result.sucesso) {
                resultDiv.innerHTML = `
                  <p class="success">${result.mensagem}</p>
                  <p class="success">Comandos agendados com sucesso para o relógio.</p>
              `;
                renderDownloads(resultDiv, result);
                alert("O processamento foi concluído! Verifique a seção de resultados.");
            } else {
                resultDiv.innerHTML = `<p class="error">${result.mensagem}</p>`;
                renderDownloads(resultDiv, result);
            }
        } catch (error) {
            progressBar.style.display = "none";
            resultDiv.style.display = "block";
            resultDiv.innerHTML = `<p class="error">Erro de conexão: ${error.message}</p>`;
        }
    });

    document.getElementById("associarRelogios").addEventListener("click", async () => {
        const fileInput = document.getElementById("arquivo");
        const matriculasInput = document.getElementById("matriculas").value.trim();
        const resultDiv = document.getElementById("result");

        resultDiv.innerHTML = "";
        resultDiv.style.display = "none";

        const formData = new FormData();
        if (fileInput.files.length > 0) {
            formData.append("arquivo", fileInput.files[0]);
        } else if (matriculasInput.length > 0) {
            const matriculas = matriculasInput
                .split(",")
                .map((m) => m.trim())
                .filter((m) => m !== "");
            if (matriculas.length === 0) {
                alert("Por favor, digite pelo menos uma matrícula válida!");
                return;
            }
            formData.append("matriculas", JSON.stringify(matriculas));
        } else {
            alert("Por favor, selecione um arquivo ou digite as matrículas!");
            return;
        }

        const relogiosSelecionados = Array.from(
            document.querySelectorAll('input[name="relogios"]:checked')
        ).map((checkbox) => parseInt(checkbox.value, 10));

        if (relogiosSelecionados.length === 0) {
            alert("Por favor, selecione pelo menos um relógio.");
            return;
        }

        formData.append("relogios", JSON.stringify(relogiosSelecionados));

        const progressBar = document.getElementById("progressBar");
        const progressBarInner = progressBar.querySelector(".progress-bar-fill");
        progressBar.style.display = "block";
        progressBarInner.textContent = "Associando relógios...";
        progressBarInner.style.backgroundColor = "#ecc94b";

        try {
            const response = await fetch("/api/envio_comando/associar", {
                method: "POST",
                body: formData,
            });

            let result;
            try {
                result = await response.json();
            } catch (e) {
                throw new Error("Resposta inválida do servidor.");
            }

            progressBar.style.display = "none";
            resultDiv.style.display = "block";

            if (!response.ok) {
                throw new Error(result.mensagem || "Erro de servidor ao processar.");
            }

            if (result.sucesso) {
                resultDiv.innerHTML = `
                  <p class="success">${result.mensagem}</p>
                  <p class="success">Crachás processados: ${result.detalhes?.crachasProcessados || 0}</p>
              `;
                renderDownloads(resultDiv, result);
                alert("A associação foi concluída! Os arquivos estão prontos para download.");
            } else {
                resultDiv.innerHTML = `<p class="error">${result.mensagem}</p>`;
                renderDownloads(resultDiv, result);
            }
        } catch (error) {
            progressBar.style.display = "none";
            resultDiv.style.display = "block";
            resultDiv.innerHTML = `<p class="error">Erro de conexão: ${error.message}</p>`;
        }
    });

    async function fetchRelogios() {
        const relogiosDiv = document.getElementById("relogios");
        relogiosDiv.innerHTML = "<em>Carregando relógios...</em>";

        try {
            const response = await fetch("/api/envio_comando/relogios");
            if (!response.ok) throw new Error("Falha ao buscar relógios.");
            const relogios = await response.json();

            relogiosDiv.innerHTML = "";

            // Adiciona checkboxes de grupos acima dos relógios
            const gruposDiv = document.createElement("div");
            gruposDiv.className = "grupos-relogios";

            Object.entries(gruposRelogios).forEach(([grupo, ids]) => {
                const label = document.createElement("label");
                label.style.fontWeight = "bold";
                const checkbox = document.createElement("input");
                checkbox.type = "checkbox";
                checkbox.className = "grupo-relogio-checkbox";
                checkbox.dataset.grupo = grupo;

                label.appendChild(checkbox);
                label.appendChild(document.createTextNode(` Selecionar grupo: ${grupo}`));
                gruposDiv.appendChild(label);

                // Lógica de seleção/desseleção do grupo
                checkbox.addEventListener("change", function () {
                    relogios.forEach((relogio) => {
                        if (ids.includes(relogio.RelogioNumero)) {
                            const cb = relogiosDiv.querySelector(
                                `input[name='relogios'][value='${relogio.RelogioNumero}']`
                            );
                            if (cb) cb.checked = this.checked;
                        }
                    });
                });
            });

            relogiosDiv.parentNode.insertBefore(gruposDiv, relogiosDiv);

            // Renderiza os relógios normalmente
            relogios.forEach((relogio) => {
                const label = document.createElement("label");
                const checkbox = document.createElement("input");
                checkbox.type = "checkbox";
                checkbox.name = "relogios";
                checkbox.value = relogio.RelogioNumero;

                label.appendChild(checkbox);
                label.appendChild(
                    document.createTextNode(` ${relogio.RelogioNumero} - ${relogio.RelogioNome}`)
                );
                relogiosDiv.appendChild(label);
            });
        } catch (error) {
            console.error("Erro ao buscar relógios:", error);
            relogiosDiv.innerHTML = `<span class="error">Falha ao carregar a lista de relógios. Verifique a conexão.</span>`;
        }
    }

    document.getElementById("selectAllRelogios").addEventListener("click", () => {
        const checkboxes = document.querySelectorAll('input[name="relogios"]');
        checkboxes.forEach((checkbox) => {
            checkbox.checked = true;
        });
    });

    document.getElementById("deselectAllRelogios").addEventListener("click", () => {
        const checkboxes = document.querySelectorAll('input[name="relogios"]');
        checkboxes.forEach((checkbox) => {
            checkbox.checked = false;
        });
        // Também limpa os checkboxes dos grupos de relógios
        const grupoCheckboxes = document.querySelectorAll('.grupo-relogio-checkbox');
        grupoCheckboxes.forEach((cb) => {
            cb.checked = false;
        });
    });

    // Call the fetch relógios API
    fetchRelogios();

    document.getElementById("desligamentoForm").addEventListener("submit", async (e) => {
        e.preventDefault();

        const fileInput = document.getElementById("arquivoDesligamento");
        const resultDiv = document.getElementById("resultDesligamento");

        resultDiv.innerHTML = "";
        resultDiv.style.display = "none";

        const formData = new FormData();
        if (!fileInput.files[0]) {
            alert("Por favor, selecione um arquivo para desligamento!");
            return;
        }
        formData.append("arquivo", fileInput.files[0]);

        const progressBar = document.getElementById("progressBarDesligamento");
        const progressBarInner = progressBar.querySelector(".progress-bar-fill");
        progressBar.style.display = "block";
        progressBarInner.textContent = "Processando Desligamento...";
        progressBarInner.style.backgroundColor = "#e53e3e"; // Red theme for dismiss

        try {
            const response = await fetch("/api/envio_comando/desligar", {
                method: "POST",
                body: formData,
            });

            let result;
            try {
                result = await response.json();
            } catch (e) {
                throw new Error("Erro de parse na resposta do servidor.");
            }

            if (!response.ok) {
                throw new Error(result.mensagem || "Erro na requisição.");
            }

            progressBar.style.display = "none";
            resultDiv.style.display = "block";

            if (result.sucesso) {
                resultDiv.innerHTML = `
                  <p class="success">${result.mensagem}</p>
                  <p class="success">Funcionários processados: ${result.processados}</p>
              `;
                renderDownloads(resultDiv, result);
                if (result.sucessoFileName || result.falhaFileName) {
                    alert("O processamento foi concluído! Os arquivos estão prontos para download.");
                }
            } else {
                resultDiv.innerHTML = `<p class="error">${result.mensagem}</p>`;
                renderDownloads(resultDiv, result);
            }
        } catch (error) {
            progressBar.style.display = "none";
            resultDiv.style.display = "block";
            resultDiv.innerHTML = `<p class="error">Erro de conexão: ${error.message}</p>`;
        }
    });

});
