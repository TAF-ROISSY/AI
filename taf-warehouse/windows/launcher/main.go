// Lanceur Windows de TAF WAREHOUSE.
//
// Trois variantes, choisies à la compilation (-ldflags "-X main.mode=…") :
//
//	online : ouvre l'application en ligne (AWS) dans sa propre fenêtre ;
//	quai   : idem, avec impression directe sans boîte de dialogue (poste du quai) ;
//	local  : démarre le serveur intégré (Python embarqué, base SQLite sur ce PC) puis ouvre la fenêtre.
package main

import (
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

var (
	mode   = "online"
	appURL = "https://yeclkv6p39.execute-api.eu-west-3.amazonaws.com"
)

func main() {
	defer func() {
		if r := recover(); r != nil {
			alert("TAF WAREHOUSE", fmt.Sprintf("Erreur inattendue : %v", r))
		}
	}()
	switch mode {
	case "local":
		runLocal()
	default:
		if err := openWindow(appURL, mode == "quai", false); err != nil {
			alert("TAF WAREHOUSE", err.Error())
		}
	}
}

// Dossier personnel de l'application : %LOCALAPPDATA%\TAF-WAREHOUSE (profil du navigateur, données locales).
func appHome(sub string) string {
	base := os.Getenv("LOCALAPPDATA")
	if base == "" {
		if h, err := os.UserHomeDir(); err == nil {
			base = filepath.Join(h, ".local", "share")
		}
	}
	dir := filepath.Join(base, "TAF-WAREHOUSE", sub)
	_ = os.MkdirAll(dir, 0o755)
	return dir
}

func findBrowser() (string, error) {
	if b := os.Getenv("TAF_BROWSER"); b != "" {
		return b, nil
	}
	var candidates []string
	if runtime.GOOS == "windows" {
		for _, root := range []string{os.Getenv("ProgramFiles(x86)"), os.Getenv("ProgramFiles"), os.Getenv("LOCALAPPDATA")} {
			if root == "" {
				continue
			}
			candidates = append(candidates,
				filepath.Join(root, `Microsoft\Edge\Application\msedge.exe`),
				filepath.Join(root, `Google\Chrome\Application\chrome.exe`))
		}
	} else {
		for _, n := range []string{"microsoft-edge", "google-chrome", "chromium", "chromium-browser"} {
			if p, err := exec.LookPath(n); err == nil {
				candidates = append(candidates, p)
			}
		}
	}
	for _, c := range candidates {
		if st, err := os.Stat(c); err == nil && !st.IsDir() {
			return c, nil
		}
	}
	return "", fmt.Errorf("Microsoft Edge ou Google Chrome est introuvable sur ce PC.\nInstallez l'un des deux puis relancez TAF WAREHOUSE.")
}

// Ouvre l'application dans une fenêtre dédiée (mode application, profil séparé).
// kiosk : impression directe sur l'imprimante par défaut, sans boîte de dialogue.
func openWindow(url string, kiosk, wait bool) error {
	browser, err := findBrowser()
	if err != nil {
		return err
	}
	profile := "profil-" + mode
	args := []string{"--app=" + url, "--user-data-dir=" + appHome(profile), "--no-first-run",
		"--no-default-browser-check", "--disable-features=Translate", "--window-size=1400,900"}
	if kiosk {
		args = append(args, "--kiosk-printing")
	}
	cmd := exec.Command(browser, args...)
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("Impossible d'ouvrir le navigateur : %v", err)
	}
	if !wait {
		return nil
	}
	started := time.Now()
	_ = cmd.Wait()
	if time.Since(started) < 5*time.Second {
		// Le navigateur a confié la fenêtre à une instance déjà ouverte : on ne peut pas suivre sa fermeture.
		alert("TAF WAREHOUSE (local)", "TAF WAREHOUSE local est en marche dans votre navigateur.\n\nCliquez sur OK quand vous avez terminé : le serveur local sera arrêté.")
	}
	return nil
}

func healthy(port int) bool {
	c := http.Client{Timeout: 2 * time.Second}
	r, err := c.Get(fmt.Sprintf("http://127.0.0.1:%d/healthz", port))
	if err != nil {
		return false
	}
	r.Body.Close()
	return r.StatusCode == 200
}

func freePort() int {
	for p := 8765; p < 8800; p++ {
		l, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", p))
		if err == nil {
			l.Close()
			return p
		}
	}
	return 0
}

func runLocal() {
	exe, _ := os.Executable()
	base := filepath.Dir(exe)
	if d := os.Getenv("TAF_LOCAL_BASE"); d != "" {
		base = d
	}
	data := appHome("donnees-locales")
	portFile := filepath.Join(data, "port.txt")

	// Déjà démarré (double clic répété) : on rouvre simplement la fenêtre.
	if b, err := os.ReadFile(portFile); err == nil {
		var p int
		fmt.Sscanf(strings.TrimSpace(string(b)), "%d", &p)
		if p > 0 && healthy(p) {
			_ = openWindow(fmt.Sprintf("http://127.0.0.1:%d/", p), false, false)
			return
		}
	}

	python := filepath.Join(base, "python", "python.exe")
	if runtime.GOOS != "windows" {
		python = "python3"
	}
	if p := os.Getenv("TAF_PYTHON"); p != "" {
		python = p
	}
	port := freePort()
	if port == 0 {
		alert("TAF WAREHOUSE (local)", "Aucun port libre entre 8765 et 8799.")
		return
	}
	logPath := filepath.Join(data, "journal-serveur.txt")
	logf, _ := os.OpenFile(logPath, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, 0o644)
	cmd := exec.Command(python, "-m", "uvicorn", "app.server:app", "--host", "127.0.0.1", "--port", fmt.Sprint(port))
	cmd.Dir = base
	cmd.Stdout, cmd.Stderr = logf, logf
	cmd.Env = append(os.Environ(),
		"TAF_DATA_DIR="+data,
		"TAF_MFA_ENABLED=0",
		"TAF_PIN_ROLES=superadmin,admin,manager,exploitation,leader,worker",
		"TAF_DEMO_RACKS=0",
		"TAF_MAIL_BACKEND=off",
		"TAF_PUBLIC_URL="+fmt.Sprintf("http://127.0.0.1:%d", port),
		"PYTHONUTF8=1", "PYTHONDONTWRITEBYTECODE=1",
	)
	hideWindow(cmd)
	if err := cmd.Start(); err != nil {
		alert("TAF WAREHOUSE (local)", "Le serveur local n'a pas pu démarrer : "+err.Error())
		return
	}
	defer cmd.Process.Kill()
	_ = os.WriteFile(portFile, []byte(fmt.Sprint(port)), 0o644)
	defer os.Remove(portFile)

	ok := false
	for i := 0; i < 120 && !ok; i++ {
		time.Sleep(500 * time.Millisecond)
		ok = healthy(port)
	}
	if !ok {
		logf.Sync()
		tail, _ := os.ReadFile(logPath)
		t := string(tail)
		if len(t) > 900 {
			t = "…" + t[len(t)-900:]
		}
		alert("TAF WAREHOUSE (local)", "Le serveur local ne répond pas.\n\nJournal : "+logPath+"\n\n"+t)
		return
	}

	// Premier démarrage : afficher le mot de passe administrateur initial, une seule fois.
	pw := filepath.Join(data, "INITIAL_ADMIN_PASSWORD.txt")
	shown := filepath.Join(data, ".mot-de-passe-affiche")
	if b, err := os.ReadFile(pw); err == nil {
		if _, err := os.Stat(shown); err != nil {
			alert("TAF WAREHOUSE (local) — premier démarrage",
				"Base locale créée sur ce PC.\n\n"+string(b)+"\nCe mot de passe est aussi enregistré dans :\n"+pw+
					"\n\nConnectez-vous avec « admin », puis créez vos utilisateurs.")
			_ = os.WriteFile(shown, []byte("1"), 0o644)
		}
	}
	if err := openWindow(fmt.Sprintf("http://127.0.0.1:%d/", port), false, true); err != nil {
		alert("TAF WAREHOUSE (local)", err.Error())
		alert("TAF WAREHOUSE (local)", fmt.Sprintf("Ouvrez http://127.0.0.1:%d dans votre navigateur.\nCliquez sur OK pour arrêter le serveur local.", port))
	}
}
