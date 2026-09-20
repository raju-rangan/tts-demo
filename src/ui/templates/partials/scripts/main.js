      });

      const driverConstructor = window.driver.js.driver;
      TOUR_DRIVER_INSTANCE = driverConstructor({
        animate: true,
        allowClose: true,
        overlayOpacity: 0.75,
        stagePadding: 6,
        stageRadius: 8,
        popoverClass: 'driverjs-theme',
        nextBtnText: 'Next &rarr;',
        prevBtnText: '&larr; Back',
        doneBtnText: 'Got It!',
        showProgress: true,
        progressText: 'Step {{current}} of {{total}}',
        steps: validSteps.length > 0 ? validSteps : steps,
        onDestroyed: () => {
          recordTourDismissal();
        }
      });

      TOUR_DRIVER_INSTANCE.drive();
    }

    // Expose for testing & console interaction
    window.startGuidedTour = startGuidedTour;
    window.resetTourStatus = resetTourStatus;
    window.resetAllTours = resetAllTours;
    window.checkAndPromptTour = checkAndPromptTour;
