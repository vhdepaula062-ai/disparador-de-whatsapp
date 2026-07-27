use pyo3::prelude::*;
use rayon::prelude::*;
use regex::Regex;

/// Extrai e valida telefones brasileiros em lote usando multithreading nativo
/// (Rayon thread pool, completamente livre do GIL do CPython).
///
/// # Argumentos
/// * `conteudos` - Lista de strings contendo texto de páginas web
///
/// # Retorno
/// Lista de tuplas `(raw_tel, tel_normalizado)` onde:
/// - `raw_tel` é o texto original capturado pelo regex
/// - `tel_normalizado` é o número limpo com DDI 55 prefixado (12-13 dígitos)
///
/// # Garantias de validação
/// - Remove todos os não-dígitos
/// - Adiciona DDI 55 se ausente
/// - Comprimento final: 12 dígitos (celular 8) ou 13 dígitos (celular 9)
/// - Descarta telefones fixos (3º dígito nacional em {2,3,4,5} para 10 dígitos)
#[pyfunction]
fn extrair_e_validar_telefones_lote(
    py: Python<'_>,
    conteudos: Vec<String>,
) -> PyResult<Vec<(String, String)>> {
    let resultados = py.allow_threads(|| {
        // Regex compilado uma única vez — Regex é thread-safe por design
        let re_tel = Regex::new(
            r"(?:\+?55\s?)?(?:\(?\d{2}\)?\s?)?(?:9\d{4}|\d{4})[-.\s]?\d{4}",
        )
        .unwrap();

        conteudos
            .par_iter()
            .flat_map(|texto| {
                let mut locais: Vec<(String, String)> = Vec::new();

                for cap in re_tel.find_iter(texto.as_str()) {
                    let raw_tel = cap.as_str().to_owned();

                    // Remove todos os não-dígitos
                    let limpo: String = raw_tel
                        .chars()
                        .filter(|c| c.is_ascii_digit())
                        .collect();

                    // Adiciona DDI 55 se ausente
                    let tel_final = if !limpo.starts_with("55") && limpo.len() >= 10 {
                        format!("55{}", limpo)
                    } else {
                        limpo.clone()
                    };

                    // Valida comprimento: 12 = 55+DDD+8dígitos, 13 = 55+DDD+9dígitos
                    if tel_final.len() < 12 || tel_final.len() > 13 {
                        continue;
                    }

                    // Filtra fixos: quando comprimento nacional é 10 e
                    // dígito na posição 4 (após 55+DDD) está em {2,3,4,5}
                    if tel_final.len() == 12 {
                        let bytes = tel_final.as_bytes();
                        if bytes.len() > 4 {
                            let quarto = bytes[4] as char;
                            if matches!(quarto, '2' | '3' | '4' | '5') {
                                continue; // Telefone fixo — descarta
                            }
                        }
                    }

                    locais.push((raw_tel, tel_final));
                }
                locais
            })
            .collect::<Vec<(String, String)>>()
    });

    Ok(resultados)
}

/// Remove duplicatas de uma lista de telefones mantendo ordem de inserção.
/// Executa em Rust puro — muito mais rápido que `dict.fromkeys()` Python
/// para listas com milhares de entradas.
#[pyfunction]
fn deduplicar_telefones(telefones: Vec<String>) -> Vec<String> {
    let mut vistos = std::collections::HashSet::with_capacity(telefones.len());
    telefones
        .into_iter()
        .filter(|t| vistos.insert(t.clone()))
        .collect()
}

/// Valida se um único número de telefone é um celular brasileiro válido.
///
/// # Regras aplicadas
/// - Aceita com ou sem DDI 55
/// - Número nacional deve ter 10 ou 11 dígitos
/// - Rejeita fixos (3º dígito nacional in {2,3,4,5} quando 10 dígitos)
///
/// # Retorno
/// `True` se for celular válido, `False` caso contrário
#[pyfunction]
fn validar_celular_brasileiro(tel: &str) -> bool {
    let limpo: String = tel.chars().filter(|c| c.is_ascii_digit()).collect();

    let nacional = if limpo.starts_with("55") && limpo.len() >= 12 {
        &limpo[2..] // remove DDI 55
    } else {
        &limpo[..]
    };

    // Comprimento nacional: 10 (DDD+8) ou 11 (DDD+9)
    if nacional.len() < 10 || nacional.len() > 11 {
        return false;
    }

    // Rejeita fixos quando 10 dígitos: 3º dígito (index 2) in {2,3,4,5}
    if nacional.len() == 10 {
        let bytes = nacional.as_bytes();
        if bytes.len() > 2 {
            let terceiro = bytes[2] as char;
            if matches!(terceiro, '2' | '3' | '4' | '5') {
                return false;
            }
        }
    }

    true
}

/// Módulo PyO3: `rust_engine`
/// Expõe 3 funções de alta performance para o Python:
///   - extrair_e_validar_telefones_lote(conteudos: list[str]) -> list[tuple[str, str]]
///   - deduplicar_telefones(telefones: list[str]) -> list[str]
///   - validar_celular_brasileiro(tel: str) -> bool
#[pymodule]
fn rust_engine(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(extrair_e_validar_telefones_lote, m)?)?;
    m.add_function(wrap_pyfunction!(deduplicar_telefones, m)?)?;
    m.add_function(wrap_pyfunction!(validar_celular_brasileiro, m)?)?;
    m.add("__version__", "0.1.0")?;
    m.add(
        "__doc__",
        "Motor nativo Rust — extração e validação paralela de telefones brasileiros.\n\
         Powered by PyO3 + Rayon. Livre do GIL do CPython.",
    )?;
    Ok(())
}
